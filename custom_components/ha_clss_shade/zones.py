"""Zone management — define and evaluate areas within the site model."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np

from .clss_data.rasterizer import SiteModel
from .shadow_engine import ShadowResult

_LOGGER = logging.getLogger(__name__)

# Classification codes
CLASS_GROUND = 2
CLASS_LOW_VEG = 3
CLASS_MED_VEG = 4
CLASS_HIGH_VEG = 5
CLASS_BUILDING = 6


@dataclass
class Zone:
    """A named area within the site model."""

    name: str
    zone_type: str  # "roof", "garden", "terrace", "custom", ...
    mask: np.ndarray  # Boolean mask (rows x cols)

    @property
    def cell_count(self) -> int:
        return int(np.sum(self.mask))

    @property
    def area_m2(self) -> float:
        """Area in square meters (requires resolution from site model)."""
        return float(self.cell_count)  # Multiply by resolution² externally

    def shade_percent(self, shadow: ShadowResult) -> float:
        """Average shade percentage in this zone."""
        if self.cell_count == 0:
            return 0.0
        return float(np.mean(shadow.shadow_map[self.mask]) * 100)

    def sun_percent(self, shadow: ShadowResult) -> float:
        """Average sun percentage in this zone."""
        return 100.0 - self.shade_percent(shadow)

    def mean_height(self, site: SiteModel) -> float:
        """Mean height above ground in this zone."""
        hag = site.height_above_ground
        if self.cell_count == 0:
            return 0.0
        return float(np.mean(hag[self.mask]))


@dataclass
class ZoneSet:
    """Collection of zones for a site."""

    zones: dict[str, Zone] = field(default_factory=dict)

    def add(self, zone: Zone) -> None:
        self.zones[zone.name] = zone

    def get(self, name: str) -> Zone | None:
        return self.zones.get(name)

    @property
    def names(self) -> list[str]:
        return list(self.zones.keys())


def auto_detect_zones(site: SiteModel) -> ZoneSet:
    """Auto-detect zones from site model classification.

    Creates zones based on LiDAR classification:
    - roof: building cells (class 6)
    - garden: ground + low vegetation within 50m of a building
    - trees: medium + high vegetation
    - open: ground cells not near buildings

    Args:
        site: Rasterized site model.

    Returns:
        ZoneSet with auto-detected zones.
    """
    cls = site.classification
    zones = ZoneSet()

    # Roof zone: building classification
    roof_mask = cls == CLASS_BUILDING
    if np.any(roof_mask):
        zones.add(Zone(name="roof", zone_type="roof", mask=roof_mask))
        _LOGGER.info("Auto-detected roof zone: %d cells", np.sum(roof_mask))

    # Expand building mask to find "near building" area
    near_building = _dilate_mask(roof_mask, radius_cells=int(50 / site.resolution))

    # Garden zone: ground + low vegetation near buildings
    ground_or_low = (cls == CLASS_GROUND) | (cls == CLASS_LOW_VEG)
    garden_mask = ground_or_low & near_building
    if np.any(garden_mask):
        zones.add(Zone(name="garden", zone_type="garden", mask=garden_mask))
        _LOGGER.info("Auto-detected garden zone: %d cells", np.sum(garden_mask))

    # Trees zone: medium + high vegetation
    trees_mask = (cls == CLASS_MED_VEG) | (cls == CLASS_HIGH_VEG)
    if np.any(trees_mask):
        zones.add(Zone(name="trees", zone_type="trees", mask=trees_mask))
        _LOGGER.info("Auto-detected trees zone: %d cells", np.sum(trees_mask))

    # Open zone: ground not near buildings
    open_mask = ground_or_low & ~near_building
    if np.any(open_mask):
        zones.add(Zone(name="open", zone_type="open", mask=open_mask))
        _LOGGER.info("Auto-detected open zone: %d cells", np.sum(open_mask))

    return zones


def create_circular_zone(
    site: SiteModel,
    name: str,
    offset_e: float = 0.0,
    offset_n: float = 0.0,
    radius_m: float = 20.0,
    zone_type: str = "custom",
) -> Zone:
    """Create a circular zone at an offset from the site center.

    Args:
        site: Site model.
        name: Zone name.
        offset_e: Offset east from center (meters).
        offset_n: Offset north from center (meters).
        radius_m: Zone radius (meters).
        zone_type: Zone type label.

    Returns:
        Zone with circular mask.
    """
    rows, cols = site.dsm.shape
    res = site.resolution

    # Center in grid coordinates
    center_row = (site.center_n - site.origin_n) / res
    center_col = (site.center_e - site.origin_e) / res

    # Offset
    target_row = center_row + offset_n / res
    target_col = center_col + offset_e / res
    radius_cells = radius_m / res

    # Build mask
    row_idx, col_idx = np.meshgrid(
        np.arange(rows, dtype=np.float32),
        np.arange(cols, dtype=np.float32),
        indexing="ij",
    )
    dist_sq = (row_idx - target_row) ** 2 + (col_idx - target_col) ** 2
    mask = dist_sq <= radius_cells**2

    return Zone(name=name, zone_type=zone_type, mask=mask)


def create_polygon_zone(
    site: SiteModel,
    name: str,
    vertices: list[tuple[float, float]],
    zone_type: str = "custom",
    coords_type: str = "offset",
) -> Zone:
    """Create a polygon zone from vertices.

    Args:
        site: Site model.
        name: Zone name.
        vertices: List of coordinate tuples. Format depends on coords_type:
            - "offset": (offset_east_m, offset_north_m) relative to center
            - "latlng": (latitude, longitude) in WGS84
        zone_type: Zone type label.
        coords_type: "offset" for meter offsets, "latlng" for GPS coordinates.

    Returns:
        Zone with polygon mask.
    """
    rows, cols = site.dsm.shape
    res = site.resolution

    # Convert vertices to grid coordinates (col, row)
    grid_vertices = []

    if coords_type == "latlng":
        from .clss_data.geo import wgs84_to_d96tm

        for lat, lon in vertices:
            e, n = wgs84_to_d96tm(lat, lon)
            col = (e - site.origin_e) / res
            row = (n - site.origin_n) / res
            grid_vertices.append((col, row))
    else:
        # Offset from center (meters)
        center_row = (site.center_n - site.origin_n) / res
        center_col = (site.center_e - site.origin_e) / res
        for offset_e, offset_n in vertices:
            col = center_col + offset_e / res
            row = center_row + offset_n / res
            grid_vertices.append((col, row))

    # Rasterize polygon using scanline fill
    mask = _rasterize_polygon(grid_vertices, rows, cols)

    zone = Zone(name=name, zone_type=zone_type, mask=mask)
    _LOGGER.info(
        "Created polygon zone '%s' (%s): %d vertices, %d cells",
        name,
        coords_type,
        len(vertices),
        zone.cell_count,
    )
    return zone


def parse_vertices(text: str) -> list[tuple[float, float]]:
    """Parse vertex text into list of (east, north) offset pairs.

    Accepts formats:
        "5,10; 15,10; 15,20; 5,20"
        "5 10; 15 10; 15 20; 5 20"
        "5,10 | 15,10 | 15,20 | 5,20"

    Returns:
        List of (offset_east, offset_north) tuples.

    Raises:
        ValueError: If the text cannot be parsed or has fewer than 3 vertices.
    """
    # Normalize separators
    text = text.strip()
    if not text:
        raise ValueError("Empty vertex string")

    # Split by semicolons or pipes
    if ";" in text:
        parts = text.split(";")
    elif "|" in text:
        parts = text.split("|")
    else:
        # Try splitting by spaces with comma-separated pairs
        parts = text.split(";")

    vertices = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        # Split each pair by comma or whitespace
        if "," in part:
            coords = part.split(",")
        else:
            coords = part.split()
        if len(coords) != 2:
            raise ValueError(f"Invalid vertex: '{part}' (expected 'east,north')")
        try:
            e = float(coords[0].strip())
            n = float(coords[1].strip())
        except ValueError:
            raise ValueError(f"Invalid coordinates in: '{part}'")
        vertices.append((e, n))

    if len(vertices) < 3:
        raise ValueError(
            f"Polygon needs at least 3 vertices, got {len(vertices)}"
        )

    return vertices


def _rasterize_polygon(
    vertices: list[tuple[float, float]], rows: int, cols: int
) -> np.ndarray:
    """Rasterize a polygon into a boolean mask using ray casting.

    Args:
        vertices: List of (col, row) grid coordinates.
        rows: Grid height.
        cols: Grid width.

    Returns:
        Boolean mask array of shape (rows, cols).
    """
    mask = np.zeros((rows, cols), dtype=bool)

    if len(vertices) < 3:
        return mask

    # Get bounding box to limit scanning
    v_cols = [v[0] for v in vertices]
    v_rows = [v[1] for v in vertices]
    min_row = max(0, int(np.floor(min(v_rows))))
    max_row = min(rows - 1, int(np.ceil(max(v_rows))))
    min_col = max(0, int(np.floor(min(v_cols))))
    max_col = min(cols - 1, int(np.ceil(max(v_cols))))

    # Use meshgrid + point-in-polygon for all cells in bounding box
    test_rows = np.arange(min_row, max_row + 1, dtype=np.float32) + 0.5
    test_cols = np.arange(min_col, max_col + 1, dtype=np.float32) + 0.5

    col_grid, row_grid = np.meshgrid(test_cols, test_rows)

    # Ray casting (crossing number algorithm) — vectorized
    n = len(vertices)
    inside = np.zeros(col_grid.shape, dtype=bool)

    for i in range(n):
        j = (i + 1) % n
        yi, xi = vertices[i][1], vertices[i][0]
        yj, xj = vertices[j][1], vertices[j][0]

        # Condition: edge crosses the horizontal ray from test point to +inf
        cond = ((yi <= row_grid) & (row_grid < yj)) | (
            (yj <= row_grid) & (row_grid < yi)
        )
        if abs(yj - yi) < 1e-10:
            continue
        x_intersect = xi + (row_grid - yi) / (yj - yi) * (xj - xi)
        crossing = cond & (col_grid < x_intersect)
        inside ^= crossing

    mask[min_row : max_row + 1, min_col : max_col + 1] = inside
    return mask


def _dilate_mask(mask: np.ndarray, radius_cells: int) -> np.ndarray:
    """Expand a boolean mask by a given radius using distance transform."""
    if not np.any(mask) or radius_cells <= 0:
        return mask
    from scipy.ndimage import distance_transform_edt

    # Distance from each cell to nearest True cell
    dist = distance_transform_edt(~mask)
    return dist <= radius_cells
