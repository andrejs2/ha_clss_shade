/**
 * CLSS Shade — 3D Terrain Viewer (Three.js)
 *
 * Renders DSM/DTM LiDAR data as an interactive 3D mesh with:
 * - Height-colored terrain (classification-based)
 * - Skirt walls for buildings (clickable facades)
 * - OrbitControls for navigation
 * - Raycaster for future 3D zone drawing
 */

import * as THREE from 'https://esm.sh/three@0.170.0';
import { OrbitControls } from 'https://esm.sh/three@0.170.0/examples/jsm/controls/OrbitControls.js';

// Classification colors (ASPRS + CLSS extended)
const CLASS_COLORS = {
  2: [0.55, 0.45, 0.35],  // Ground — brown
  3: [0.45, 0.70, 0.30],  // Low vegetation — light green
  4: [0.30, 0.60, 0.20],  // Medium vegetation — green
  5: [0.15, 0.45, 0.10],  // High vegetation — dark green
  6: [0.70, 0.65, 0.60],  // Building — light gray
  9: [0.30, 0.50, 0.80],  // Water — blue
  10: [0.60, 0.60, 0.70], // Bridges — blue-gray
  14: [0.90, 0.80, 0.10], // Power lines — yellow
  15: [0.75, 0.55, 0.20], // Transmission towers — orange
  17: [0.60, 0.60, 0.70], // Bridges (alt code) — blue-gray
  20: [0.85, 0.50, 0.20], // Small objects — orange
};
const DEFAULT_COLOR = [0.50, 0.50, 0.50];

export class TerrainViewer {
  constructor(container) {
    this.container = container;
    this.scene = null;
    this.camera = null;
    this.renderer = null;
    this.controls = null;
    this.terrainGroup = null;
    this.raycaster = new THREE.Raycaster();
    this.mouse = new THREE.Vector2();
    this.terrainData = null;
    this._animating = false;

    // Point cloud state
    this.pointCloudGroup = null;
    this._pointSize = 1.5;

    // Zone drawing state
    this.drawingMode = false;
    this.currentZonePoints = [];    // [{x,y,z}, ...]
    this.currentZoneMarkers = [];   // Three.js spheres
    this.currentZoneLines = null;   // Three.js Line
    this.completedZones = [];       // [{name, points, mesh}, ...]

    // Zone editing state
    this.editingMode = false;
    this.editingZoneIndex = -1;
    this._editHandles = [];         // Three.js sphere handles
    this._editOutline = null;       // Three.js Line for edit outline
    this._dragHandle = null;        // currently dragged handle
  }

  init() {
    const w = this.container.clientWidth;
    const h = this.container.clientHeight;

    // Scene
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0x1a1a2e);
    this.scene.fog = new THREE.Fog(0x1a1a2e, 800, 2000);

    // Camera
    this.camera = new THREE.PerspectiveCamera(50, w / h, 0.5, 3000);
    this.camera.position.set(0, 200, 200);
    this.camera.lookAt(0, 0, 0);

    // Renderer
    this.renderer = new THREE.WebGLRenderer({ antialias: true });
    this.renderer.setSize(w, h);
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    this.container.appendChild(this.renderer.domElement);

    // Controls
    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.1;
    this.controls.maxPolarAngle = Math.PI * 0.48;
    this.controls.minDistance = 10;
    this.controls.maxDistance = 1500;

    // Lighting
    const ambient = new THREE.AmbientLight(0xffffff, 0.4);
    this.scene.add(ambient);

    const sun = new THREE.DirectionalLight(0xffffff, 1.0);
    sun.position.set(100, 200, 80);
    sun.castShadow = true;
    sun.shadow.mapSize.set(2048, 2048);
    sun.shadow.camera.left = -300;
    sun.shadow.camera.right = 300;
    sun.shadow.camera.top = 300;
    sun.shadow.camera.bottom = -300;
    this.scene.add(sun);

    // Hemisphere light for sky/ground color
    const hemi = new THREE.HemisphereLight(0x87ceeb, 0x444422, 0.3);
    this.scene.add(hemi);

    // Grid helper at ground level
    const grid = new THREE.GridHelper(400, 40, 0x444444, 0x333333);
    grid.position.y = -0.5;
    this.scene.add(grid);

    // Resize handler
    this._onResize = () => {
      const w = this.container.clientWidth;
      const h = this.container.clientHeight;
      this.camera.aspect = w / h;
      this.camera.updateProjectionMatrix();
      this.renderer.setSize(w, h);
    };
    window.addEventListener('resize', this._onResize);

    // Click handler for raycasting
    this.renderer.domElement.addEventListener('click', (e) => this._onClick(e));

    // Drag handlers for edit mode
    this.renderer.domElement.addEventListener('pointerdown', (e) => this._onPointerDown(e));
    this.renderer.domElement.addEventListener('pointermove', (e) => this._onPointerMove(e));
    this.renderer.domElement.addEventListener('pointerup', (e) => this._onPointerUp(e));

    this._animate();
  }

  /**
   * Load terrain data from WebSocket response.
   * @param {Object} data - {rows, cols, resolution, dsm_b64, dtm_b64, classification_b64, ...}
   */
  loadTerrain(data) {
    this.terrainData = data;

    // Decode base64 arrays
    const rows = data.rows;
    const cols = data.cols;
    const res = data.resolution;
    const dsm = new Float32Array(Uint8Array.from(atob(data.dsm_b64), c => c.charCodeAt(0)).buffer);
    const dtm = new Float32Array(Uint8Array.from(atob(data.dtm_b64), c => c.charCodeAt(0)).buffer);
    const cls = new Uint8Array(Uint8Array.from(atob(data.classification_b64), c => c.charCodeAt(0)).buffer);

    // Remove old terrain
    if (this.terrainGroup) {
      this.scene.remove(this.terrainGroup);
      this.terrainGroup.traverse(c => { if (c.geometry) c.geometry.dispose(); if (c.material) c.material.dispose(); });
    }
    this.terrainGroup = new THREE.Group();

    // --- Build ground mesh from DTM ---
    const groundGeo = new THREE.PlaneGeometry(
      cols * res, rows * res,
      cols - 1, rows - 1
    );
    groundGeo.rotateX(-Math.PI / 2);

    const groundPos = groundGeo.attributes.position.array;
    const groundColors = new Float32Array(groundPos.length);

    // Compute height range for normalization
    let minH = Infinity, maxH = -Infinity;
    for (let i = 0; i < dsm.length; i++) {
      if (dsm[i] > maxH) maxH = dsm[i];
      if (dtm[i] < minH) minH = dtm[i];
    }
    const baseH = minH;

    // Build a mask of cells with real data (classification > 0)
    const hasData = new Uint8Array(rows * cols);
    for (let i = 0; i < cls.length; i++) hasData[i] = cls[i] > 0 ? 1 : 0;

    // Scene background color for no-data cells (blend in, no huge triangles)
    const BG = [0.10, 0.10, 0.18];

    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        const gridIdx = r * cols + c;
        const vertIdx = (rows - 1 - r) * cols + c;
        const vi3 = vertIdx * 3;

        if (!hasData[gridIdx]) {
          // Keep at DTM height (gap-filled) but color as background
          groundPos[vi3 + 1] = dtm[gridIdx] - baseH;
          groundColors[vi3] = BG[0]; groundColors[vi3 + 1] = BG[1]; groundColors[vi3 + 2] = BG[2];
          continue;
        }

        groundPos[vi3 + 1] = dtm[gridIdx] - baseH;

        const clsCode = cls[gridIdx];
        const rgb = CLASS_COLORS[clsCode] || DEFAULT_COLOR;
        groundColors[vi3] = rgb[0];
        groundColors[vi3 + 1] = rgb[1];
        groundColors[vi3 + 2] = rgb[2];
      }
    }

    groundGeo.setAttribute('color', new THREE.BufferAttribute(groundColors, 3));
    groundGeo.computeVertexNormals();

    const groundMat = new THREE.MeshLambertMaterial({
      vertexColors: true,
      side: THREE.DoubleSide,
    });
    const groundMesh = new THREE.Mesh(groundGeo, groundMat);
    groundMesh.receiveShadow = true;
    groundMesh.name = 'ground';
    this.terrainGroup.add(groundMesh);

    // Load satellite texture onto ground mesh
    if (data.bounds_sw && data.bounds_ne) {
      this._loadSatelliteTexture(groundMesh, data.bounds_sw, data.bounds_ne, cols, rows);
    }

    // --- Build separate meshes for buildings and vegetation ---
    // Individual quads per elevated cell (no shared edges → no transitional slopes)
    const ELEV_THRESHOLD = 1.5;
    const halfW = cols * res / 2;
    const halfH = rows * res / 2;

    for (const [layerName, classSet, colorBright] of [
      ['buildings', new Set([6]), 1.15],
      ['vegetation', new Set([3, 4, 5]), 1.1],
    ]) {
      const positions = [];
      const colors = [];

      for (let r = 0; r < rows; r++) {
        for (let c = 0; c < cols; c++) {
          const idx = r * cols + c;
          if (!hasData[idx]) continue;
          const hag = dsm[idx] - dtm[idx];
          if (hag < ELEV_THRESHOLD || !classSet.has(cls[idx])) continue;

          const y = dsm[idx] - baseH;
          // Quad corners (in viewer coords, centered)
          const x0 = c * res - halfW;
          const x1 = (c + 1) * res - halfW;
          const z0 = (rows - 1 - r) * res - halfH;
          const z1 = (rows - r) * res - halfH;

          // Two triangles for the quad (top face)
          positions.push(
            x0, y, z0,  x1, y, z0,  x0, y, z1,
            x1, y, z0,  x1, y, z1,  x0, y, z1,
          );

          const rgb = CLASS_COLORS[cls[idx]] || DEFAULT_COLOR;
          const cr = Math.min(1, rgb[0] * colorBright);
          const cg = Math.min(1, rgb[1] * colorBright);
          const cb = Math.min(1, rgb[2] * colorBright);
          for (let v = 0; v < 6; v++) colors.push(cr, cg, cb);
        }
      }

      if (positions.length === 0) continue;

      const geo = new THREE.BufferGeometry();
      geo.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
      geo.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3));
      geo.computeVertexNormals();

      const mat = new THREE.MeshLambertMaterial({
        vertexColors: true,
        side: THREE.DoubleSide,
      });
      const mesh = new THREE.Mesh(geo, mat);
      mesh.castShadow = true;
      mesh.receiveShadow = true;
      mesh.name = layerName;
      this.terrainGroup.add(mesh);
    }

    // --- Build skirt walls for buildings ---
    this._buildSkirtWalls(dsm, dtm, cls, rows, cols, res, baseH);

    this.scene.add(this.terrainGroup);

    // Center camera on terrain
    const cx = 0, cy = (maxH - baseH) * 0.5, cz = 0;
    this.controls.target.set(cx, cy, cz);
    const dist = Math.max(cols, rows) * res * 0.6;
    this.camera.position.set(cx + dist * 0.4, cy + dist * 0.5, cz + dist * 0.6);
    this.controls.update();

    console.log(`Terrain loaded: ${rows}×${cols}, res=${res}m, height ${minH.toFixed(1)}-${maxH.toFixed(1)}m`);
  }

  /**
   * Load point cloud data from WebSocket response.
   * @param {Object} data - {num_points, positions_b64, classification_b64}
   */
  loadPointCloud(data) {
    if (data.num_points === 0) {
      console.warn('Point cloud: no points received');
      return;
    }

    // Remove old point cloud
    if (this.pointCloudGroup) {
      this.scene.remove(this.pointCloudGroup);
      this.pointCloudGroup.traverse(c => {
        if (c.geometry) c.geometry.dispose();
        if (c.material) c.material.dispose();
      });
    }
    this.pointCloudGroup = new THREE.Group();
    this.pointCloudGroup.name = 'pointcloud';

    // Decode base64 arrays
    const positions = new Float32Array(
      Uint8Array.from(atob(data.positions_b64), c => c.charCodeAt(0)).buffer
    );
    const cls = new Uint8Array(
      Uint8Array.from(atob(data.classification_b64), c => c.charCodeAt(0)).buffer
    );
    const numPts = data.num_points;

    // Build color array: prefer real RGB from LiDAR, fall back to classification
    const colors = new Float32Array(numPts * 3);
    if (data.has_rgb && data.rgb_b64) {
      const rgb = new Uint8Array(
        Uint8Array.from(atob(data.rgb_b64), c => c.charCodeAt(0)).buffer
      );
      for (let i = 0; i < numPts; i++) {
        colors[i * 3] = rgb[i * 3] / 255;
        colors[i * 3 + 1] = rgb[i * 3 + 1] / 255;
        colors[i * 3 + 2] = rgb[i * 3 + 2] / 255;
      }
      console.log('Point cloud: using real RGB colors from LiDAR');
    } else {
      for (let i = 0; i < numPts; i++) {
        const c = CLASS_COLORS[cls[i]] || DEFAULT_COLOR;
        colors[i * 3] = c[0];
        colors[i * 3 + 1] = c[1];
        colors[i * 3 + 2] = c[2];
      }
      console.log('Point cloud: using classification colors (no RGB in data)');
    }

    // Create Points geometry
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
    geo.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3));

    const mat = new THREE.PointsMaterial({
      size: this._pointSize,
      sizeAttenuation: true,
      vertexColors: true,
    });

    const points = new THREE.Points(geo, mat);
    points.name = 'points';
    this.pointCloudGroup.add(points);

    this.scene.add(this.pointCloudGroup);

    // Hide terrain mesh layers when point cloud is shown
    if (this.terrainGroup) {
      for (const layer of ['buildings', 'vegetation', 'walls']) {
        this.toggleLayer(layer, false);
      }
    }

    console.log(`Point cloud loaded: ${numPts.toLocaleString()} points, size=${this._pointSize}`);
  }

  /**
   * Set point cloud point size.
   * @param {number} size - Point size (0.5 to 5.0)
   */
  setPointSize(size) {
    this._pointSize = size;
    if (this.pointCloudGroup) {
      this.pointCloudGroup.traverse(c => {
        if (c.material && c.material.size !== undefined) {
          c.material.size = size;
        }
      });
    }
  }

  /**
   * Toggle point cloud visibility.
   * @param {boolean} visible
   */
  togglePointCloud(visible) {
    if (this.pointCloudGroup) {
      this.pointCloudGroup.visible = visible;
    }
  }

  /**
   * Check if point cloud is loaded and visible.
   */
  hasPointCloud() {
    return this.pointCloudGroup !== null && this.pointCloudGroup.visible;
  }

  _loadSatelliteTexture(mesh, sw, ne, cols, rows) {
    // Fetch satellite imagery from Esri World Imagery via Image element
    // (avoids CORS issues with TextureLoader)
    const imgSize = Math.min(2048, Math.max(cols, rows) * 2);
    const bbox = `${sw[1]},${sw[0]},${ne[1]},${ne[0]}`;
    const url = `https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/export?`
      + `bbox=${bbox}&bboxSR=4326&size=${imgSize},${imgSize}`
      + `&imageSR=4326&format=png&f=image`;

    console.log('Loading satellite texture:', url.substring(0, 80) + '...');

    const img = new Image();
    img.crossOrigin = 'anonymous';
    img.onload = () => {
      const texture = new THREE.Texture(img);
      texture.needsUpdate = true;
      texture.minFilter = THREE.LinearFilter;
      texture.magFilter = THREE.LinearFilter;
      mesh.material.dispose();
      mesh.material = new THREE.MeshLambertMaterial({
        map: texture,
        side: THREE.DoubleSide,
      });
      console.log(`Satellite texture loaded: ${img.width}x${img.height}`);
    };
    img.onerror = (err) => {
      console.warn('Satellite texture failed, keeping classification colors', err);
    };
    img.src = url;
  }

  _buildSkirtWalls(dsm, dtm, cls, rows, cols, res, baseH) {
    const wallPositions = [];
    const wallColors = [];
    const WALL_THRESHOLD = 1.5; // min height difference to create wall
    const halfW = cols * res / 2;
    const halfH = rows * res / 2;

    const wallColor = [0.60, 0.55, 0.50]; // building wall color

    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        const idx = r * cols + c;
        const hag = dsm[idx] - dtm[idx];
        if (hag < WALL_THRESHOLD) continue;
        if (cls[idx] !== 6) continue; // only buildings

        // Check 4 neighbors — create wall quad where building meets ground
        const neighbors = [
          [r - 1, c], [r + 1, c], [r, c - 1], [r, c + 1]
        ];

        for (const [nr, nc] of neighbors) {
          if (nr < 0 || nr >= rows || nc < 0 || nc >= cols) continue;
          const nIdx = nr * cols + nc;
          const nHag = dsm[nIdx] - dtm[nIdx];
          if (nHag >= WALL_THRESHOLD && cls[nIdx] === 6) continue; // neighbor is also building

          // Create wall quad: from ground to roof at this edge
          const top = dsm[idx] - baseH;
          const bot = dtm[idx] - baseH;

          // Wall position in world coords (centered)
          const x1 = c * res - halfW;
          const x2 = (nr === r) ? x1 : (c + (nr > r ? 0.5 : -0.5)) * res - halfW;
          const z1 = (rows - 1 - r) * res - halfH;
          const z2 = (nr === r) ? ((rows - 1 - r) + (nc > c ? 0.5 : -0.5)) * res - halfH : z1;

          // Two triangles for the quad
          wallPositions.push(
            x1, bot, z1,  x2, bot, z2,  x1, top, z1,
            x2, bot, z2,  x2, top, z2,  x1, top, z1,
          );

          for (let t = 0; t < 6; t++) {
            wallColors.push(...wallColor);
          }
        }
      }
    }

    if (wallPositions.length === 0) return;

    const wallGeo = new THREE.BufferGeometry();
    wallGeo.setAttribute('position', new THREE.Float32BufferAttribute(wallPositions, 3));
    wallGeo.setAttribute('color', new THREE.Float32BufferAttribute(wallColors, 3));
    wallGeo.computeVertexNormals();

    const wallMat = new THREE.MeshLambertMaterial({
      vertexColors: true,
      side: THREE.DoubleSide,
    });
    const wallMesh = new THREE.Mesh(wallGeo, wallMat);
    wallMesh.castShadow = true;
    wallMesh.name = 'walls';
    this.terrainGroup.add(wallMesh);

    console.log(`Skirt walls: ${wallPositions.length / 18} quads`);
  }

  // ─── Layer Visibility ───

  toggleLayer(name, visible) {
    if (!this.terrainGroup) return;
    this.terrainGroup.traverse(c => {
      if (c.name === name) c.visible = visible;
    });
  }

  getLayerNames() {
    return ['ground', 'buildings', 'vegetation', 'walls'];
  }

  isLayerVisible(name) {
    let vis = true;
    if (!this.terrainGroup) return vis;
    this.terrainGroup.traverse(c => {
      if (c.name === name) vis = c.visible;
    });
    return vis;
  }

  // ─── Zone Drawing ───

  startDrawing() {
    this.drawingMode = true;
    this.currentZonePoints = [];
    this._clearCurrentMarkers();
    this.controls.enableRotate = true; // still allow orbit
    this.container.dispatchEvent(new CustomEvent('draw-start'));
  }

  cancelDrawing() {
    this.drawingMode = false;
    this.currentZonePoints = [];
    this._clearCurrentMarkers();
    this.container.dispatchEvent(new CustomEvent('draw-cancel'));
  }

  finishDrawing(zoneName, zoneColor) {
    if (this.currentZonePoints.length < 3) {
      this.cancelDrawing();
      return null;
    }

    const points = [...this.currentZonePoints];
    const mesh = this._createZonePolygonMesh(points, zoneColor || '#2196F3');
    this.scene.add(mesh);

    const zone = { name: zoneName, color: zoneColor, points, mesh };
    this.completedZones.push(zone);

    this.drawingMode = false;
    this.currentZonePoints = [];
    this._clearCurrentMarkers();

    this.container.dispatchEvent(new CustomEvent('draw-finish', {
      detail: { name: zoneName, points }
    }));

    return zone;
  }

  _addDrawPoint(point) {
    this.currentZonePoints.push({ x: point.x, y: point.y, z: point.z });

    // Red sphere marker
    const sphere = new THREE.Mesh(
      new THREE.SphereGeometry(0.6, 12, 12),
      new THREE.MeshBasicMaterial({ color: 0xff2222 })
    );
    sphere.position.copy(point);
    this.scene.add(sphere);
    this.currentZoneMarkers.push(sphere);

    // Update connecting line
    this._updateDrawLine();

    this.container.dispatchEvent(new CustomEvent('draw-point', {
      detail: {
        x: point.x, y: point.y, z: point.z,
        count: this.currentZonePoints.length
      }
    }));
  }

  _updateDrawLine() {
    // Remove old line
    if (this.currentZoneLines) {
      this.scene.remove(this.currentZoneLines);
      this.currentZoneLines.geometry.dispose();
    }

    if (this.currentZonePoints.length < 2) return;

    const linePoints = this.currentZonePoints.map(
      p => new THREE.Vector3(p.x, p.y, p.z)
    );
    // Close the loop preview
    linePoints.push(linePoints[0].clone());

    const geo = new THREE.BufferGeometry().setFromPoints(linePoints);
    const mat = new THREE.LineBasicMaterial({ color: 0xff4444, linewidth: 2 });
    this.currentZoneLines = new THREE.Line(geo, mat);
    this.scene.add(this.currentZoneLines);
  }

  _clearCurrentMarkers() {
    for (const m of this.currentZoneMarkers) {
      this.scene.remove(m);
      m.geometry.dispose();
      m.material.dispose();
    }
    this.currentZoneMarkers = [];
    if (this.currentZoneLines) {
      this.scene.remove(this.currentZoneLines);
      this.currentZoneLines.geometry.dispose();
      this.currentZoneLines = null;
    }
  }

  _createZonePolygonMesh(points, color) {
    // Create a semi-transparent polygon mesh from 3D points
    // Uses fan triangulation from centroid
    const group = new THREE.Group();
    group.name = 'zone';

    const cx = points.reduce((s, p) => s + p.x, 0) / points.length;
    const cy = points.reduce((s, p) => s + p.y, 0) / points.length;
    const cz = points.reduce((s, p) => s + p.z, 0) / points.length;

    const positions = [];
    for (let i = 0; i < points.length; i++) {
      const a = points[i];
      const b = points[(i + 1) % points.length];
      positions.push(cx, cy, cz, a.x, a.y, a.z, b.x, b.y, b.z);
    }

    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
    geo.computeVertexNormals();

    const col = new THREE.Color(color);
    const mat = new THREE.MeshBasicMaterial({
      color: col, transparent: true, opacity: 0.35,
      side: THREE.DoubleSide, depthWrite: false,
    });
    group.add(new THREE.Mesh(geo, mat));

    // Outline
    const outlinePoints = points.map(p => new THREE.Vector3(p.x, p.y, p.z));
    outlinePoints.push(outlinePoints[0].clone());
    const lineGeo = new THREE.BufferGeometry().setFromPoints(outlinePoints);
    const lineMat = new THREE.LineBasicMaterial({ color: col, linewidth: 2 });
    group.add(new THREE.Line(lineGeo, lineMat));

    // Corner spheres
    for (const p of points) {
      const s = new THREE.Mesh(
        new THREE.SphereGeometry(0.4, 8, 8),
        new THREE.MeshBasicMaterial({ color: col })
      );
      s.position.set(p.x, p.y, p.z);
      group.add(s);
    }

    return group;
  }

  // ─── Zone Editing ───

  startEditing(zoneIndex) {
    if (zoneIndex < 0 || zoneIndex >= this.completedZones.length) return;
    this.editingMode = true;
    this.editingZoneIndex = zoneIndex;
    this._showEditHandles(zoneIndex);
    this.container.dispatchEvent(new CustomEvent('edit-start', {
      detail: { index: zoneIndex, name: this.completedZones[zoneIndex].name }
    }));
  }

  finishEditing() {
    if (!this.editingMode) return;
    const zone = this.completedZones[this.editingZoneIndex];
    this._hideEditHandles();
    // Rebuild zone mesh with updated points
    if (zone.mesh) {
      this.scene.remove(zone.mesh);
      zone.mesh.traverse(c => { if (c.geometry) c.geometry.dispose(); if (c.material) c.material.dispose(); });
    }
    zone.mesh = this._createZonePolygonMesh(zone.points, zone.color || '#2196F3');
    this.scene.add(zone.mesh);
    this.editingMode = false;
    const idx = this.editingZoneIndex;
    this.editingZoneIndex = -1;
    this.container.dispatchEvent(new CustomEvent('edit-finish', {
      detail: { index: idx, name: zone.name, points: zone.points }
    }));
  }

  cancelEditing() {
    if (!this.editingMode) return;
    this._hideEditHandles();
    this.editingMode = false;
    this.editingZoneIndex = -1;
    this.container.dispatchEvent(new CustomEvent('edit-cancel'));
  }

  _showEditHandles(zoneIndex) {
    this._hideEditHandles();
    const zone = this.completedZones[zoneIndex];
    for (let i = 0; i < zone.points.length; i++) {
      const p = zone.points[i];
      const handle = new THREE.Mesh(
        new THREE.SphereGeometry(1.0, 16, 16),
        new THREE.MeshBasicMaterial({ color: 0xffff00, depthTest: false })
      );
      handle.position.set(p.x, p.y, p.z);
      handle.renderOrder = 999;
      handle.userData.pointIndex = i;
      handle.userData.isEditHandle = true;
      this.scene.add(handle);
      this._editHandles.push(handle);
    }
    // Dim the zone mesh while editing
    if (zone.mesh) zone.mesh.visible = false;
    // Show edit outline
    this._updateEditOutline(zone.points);
  }

  _hideEditHandles() {
    for (const h of this._editHandles) {
      this.scene.remove(h);
      h.geometry.dispose();
      h.material.dispose();
    }
    this._editHandles = [];
    if (this._editOutline) {
      this.scene.remove(this._editOutline);
      this._editOutline.geometry.dispose();
      this._editOutline = null;
    }
    // Restore zone mesh visibility
    if (this.editingZoneIndex >= 0) {
      const zone = this.completedZones[this.editingZoneIndex];
      if (zone && zone.mesh) zone.mesh.visible = true;
    }
  }

  _updateEditOutline(points) {
    if (this._editOutline) {
      this.scene.remove(this._editOutline);
      this._editOutline.geometry.dispose();
    }
    if (points.length < 2) return;
    const verts = points.map(p => new THREE.Vector3(p.x, p.y, p.z));
    verts.push(verts[0].clone());
    const geo = new THREE.BufferGeometry().setFromPoints(verts);
    const mat = new THREE.LineBasicMaterial({ color: 0xffff00, linewidth: 2, depthTest: false });
    this._editOutline = new THREE.Line(geo, mat);
    this._editOutline.renderOrder = 998;
    this.scene.add(this._editOutline);
  }

  _onPointerDown(event) {
    if (!this.editingMode) return;
    const rect = this.renderer.domElement.getBoundingClientRect();
    this.mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    this.mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
    this.raycaster.setFromCamera(this.mouse, this.camera);

    const hits = this.raycaster.intersectObjects(this._editHandles);
    if (hits.length > 0) {
      this._dragHandle = hits[0].object;
      this.controls.enabled = false; // disable orbit while dragging
      event.preventDefault();
      event.stopPropagation();
    }
  }

  _onPointerMove(event) {
    if (!this._dragHandle) return;
    // Raycast against terrain to find new position
    const rect = this.renderer.domElement.getBoundingClientRect();
    this.mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    this.mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
    this.raycaster.setFromCamera(this.mouse, this.camera);

    if (!this.terrainGroup) return;
    const meshes = [];
    this.terrainGroup.traverse(c => { if (c.isMesh) meshes.push(c); });
    const hits = this.raycaster.intersectObjects(meshes);
    if (hits.length > 0) {
      const newPos = hits[0].point;
      this._dragHandle.position.copy(newPos);
      // Update zone point data
      const idx = this._dragHandle.userData.pointIndex;
      const zone = this.completedZones[this.editingZoneIndex];
      zone.points[idx] = { x: newPos.x, y: newPos.y, z: newPos.z };
      this._updateEditOutline(zone.points);
    }
    event.preventDefault();
  }

  _onPointerUp(event) {
    if (this._dragHandle) {
      this._dragHandle = null;
      this.controls.enabled = true;
      this.container.dispatchEvent(new CustomEvent('edit-point-moved', {
        detail: { index: this.editingZoneIndex }
      }));
    }
  }

  // ─── Raycasting ───

  _raycastTerrain(event) {
    const rect = this.renderer.domElement.getBoundingClientRect();
    this.mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    this.mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

    this.raycaster.setFromCamera(this.mouse, this.camera);

    if (!this.terrainGroup) return null;
    const meshes = [];
    this.terrainGroup.traverse(c => { if (c.isMesh) meshes.push(c); });

    const intersects = this.raycaster.intersectObjects(meshes);
    if (intersects.length > 0) {
      return { point: intersects[0].point, meshName: intersects[0].object.name || '?' };
    }
    return null;
  }

  _onClick(event) {
    if (this.editingMode) return; // handled by pointer events

    const hit = this._raycastTerrain(event);
    if (!hit) return;

    const { point, meshName } = hit;

    if (this.drawingMode) {
      this._addDrawPoint(point);
      return;
    }

    // Not drawing — just info click
    console.log(`3D click: (${point.x.toFixed(1)}, ${point.y.toFixed(1)}, ${point.z.toFixed(1)}) on ${meshName}`);
    this.container.dispatchEvent(new CustomEvent('terrain-click', {
      detail: { x: point.x, y: point.y, z: point.z, meshName }
    }));
  }

  _animate() {
    if (!this._animating) {
      this._animating = true;
    }
    requestAnimationFrame(() => this._animate());
    this.controls.update();
    this.renderer.render(this.scene, this.camera);
  }

  dispose() {
    this._animating = false;
    window.removeEventListener('resize', this._onResize);
    if (this.pointCloudGroup) {
      this.pointCloudGroup.traverse(c => {
        if (c.geometry) c.geometry.dispose();
        if (c.material) c.material.dispose();
      });
    }
    if (this.renderer) {
      this.renderer.dispose();
      this.renderer.domElement.remove();
    }
    if (this.controls) this.controls.dispose();
  }
}
