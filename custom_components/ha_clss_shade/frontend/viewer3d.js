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

// Classification colors (ASPRS)
const CLASS_COLORS = {
  2: [0.55, 0.45, 0.35],  // Ground — brown
  3: [0.45, 0.70, 0.30],  // Low vegetation — light green
  4: [0.30, 0.60, 0.20],  // Medium vegetation — green
  5: [0.15, 0.45, 0.10],  // High vegetation — dark green
  6: [0.70, 0.65, 0.60],  // Building — light gray
  9: [0.30, 0.50, 0.80],  // Water — blue
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
  }

  init() {
    const w = this.container.clientWidth;
    const h = this.container.clientHeight;

    // Scene
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0x1a1a2e);
    this.scene.fog = new THREE.Fog(0x1a1a2e, 500, 1200);

    // Camera
    this.camera = new THREE.PerspectiveCamera(50, w / h, 0.5, 2000);
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
    this.controls.maxDistance = 800;

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

    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        const gridIdx = r * cols + c;
        // PlaneGeometry vertex order: row 0 = top (north), increasing south
        // Our grid: row 0 = south. So flip: vertexRow = rows-1-r
        const vertIdx = (rows - 1 - r) * cols + c;
        const vi3 = vertIdx * 3;

        // Y = height (up), subtract base to center vertically
        groundPos[vi3 + 1] = dtm[gridIdx] - baseH;

        // Color by classification
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

    // --- Build surface mesh from DSM (buildings, trees on top of ground) ---
    const surfGeo = new THREE.PlaneGeometry(
      cols * res, rows * res,
      cols - 1, rows - 1
    );
    surfGeo.rotateX(-Math.PI / 2);

    const surfPos = surfGeo.attributes.position.array;
    const surfColors = new Float32Array(surfPos.length);

    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        const gridIdx = r * cols + c;
        const vertIdx = (rows - 1 - r) * cols + c;
        const vi3 = vertIdx * 3;

        surfPos[vi3 + 1] = dsm[gridIdx] - baseH;

        const clsCode = cls[gridIdx];
        const rgb = CLASS_COLORS[clsCode] || DEFAULT_COLOR;

        // Brighten elevated features slightly
        const hag = dsm[gridIdx] - dtm[gridIdx];
        const bright = hag > 1.5 ? 1.15 : 1.0;
        surfColors[vi3] = Math.min(1, rgb[0] * bright);
        surfColors[vi3 + 1] = Math.min(1, rgb[1] * bright);
        surfColors[vi3 + 2] = Math.min(1, rgb[2] * bright);
      }
    }

    surfGeo.setAttribute('color', new THREE.BufferAttribute(surfColors, 3));
    surfGeo.computeVertexNormals();

    const surfMat = new THREE.MeshLambertMaterial({
      vertexColors: true,
      side: THREE.DoubleSide,
    });
    const surfMesh = new THREE.Mesh(surfGeo, surfMat);
    surfMesh.castShadow = true;
    surfMesh.receiveShadow = true;
    surfMesh.name = 'surface';
    this.terrainGroup.add(surfMesh);

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

  _onClick(event) {
    const rect = this.renderer.domElement.getBoundingClientRect();
    this.mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    this.mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

    this.raycaster.setFromCamera(this.mouse, this.camera);

    if (!this.terrainGroup) return;
    const meshes = [];
    this.terrainGroup.traverse(c => { if (c.isMesh) meshes.push(c); });

    const intersects = this.raycaster.intersectObjects(meshes);
    if (intersects.length > 0) {
      const hit = intersects[0];
      const p = hit.point;
      const meshName = hit.object.name || '?';
      console.log(`3D click: (${p.x.toFixed(1)}, ${p.y.toFixed(1)}, ${p.z.toFixed(1)}) on ${meshName}`);

      // Visual feedback: small sphere at click point
      const sphere = new THREE.Mesh(
        new THREE.SphereGeometry(0.5, 8, 8),
        new THREE.MeshBasicMaterial({ color: 0xff2222 })
      );
      sphere.position.copy(p);
      this.scene.add(sphere);

      // Dispatch custom event for zone drawing integration
      this.container.dispatchEvent(new CustomEvent('terrain-click', {
        detail: { x: p.x, y: p.y, z: p.z, meshName }
      }));
    }
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
    if (this.renderer) {
      this.renderer.dispose();
      this.renderer.domElement.remove();
    }
    if (this.controls) this.controls.dispose();
  }
}
