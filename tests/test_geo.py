"""Tests for geo.py coordinate transforms and tile utilities."""

from __future__ import annotations

import sys
sys.path.insert(0, "custom_components")

from ha_clss_shade.clss_data.geo import (
    d96tm_to_wgs84,
    get_tile_coords,
    get_tiles_for_radius,
    is_in_slovenia,
    tile_filename,
    wgs84_to_d96tm,
)

# Known reference points (from GURS documentation / online converters)
# Ljubljana castle: lat 46.0489, lon 14.5087
# Approximate D96/TM: E~462000, N~101000

LJUBLJANA = (46.0489, 14.5087)
MARIBOR = (46.5547, 15.6459)
KOPER = (45.5469, 13.7302)
VIENNA = (48.2082, 16.3738)  # Outside Slovenia


def test_is_in_slovenia():
    assert is_in_slovenia(*LJUBLJANA)
    assert is_in_slovenia(*MARIBOR)
    assert is_in_slovenia(*KOPER)
    assert not is_in_slovenia(*VIENNA)
    print("PASS: is_in_slovenia")


def test_wgs84_to_d96tm_roundtrip():
    """Test that WGS84 -> D96/TM -> WGS84 roundtrip preserves coordinates."""
    for name, (lat, lon) in [("Ljubljana", LJUBLJANA), ("Maribor", MARIBOR), ("Koper", KOPER)]:
        e, n = wgs84_to_d96tm(lat, lon)
        lat2, lon2 = d96tm_to_wgs84(e, n)
        assert abs(lat - lat2) < 1e-8, f"{name}: lat diff {abs(lat - lat2)}"
        assert abs(lon - lon2) < 1e-8, f"{name}: lon diff {abs(lon - lon2)}"
        print(f"PASS: roundtrip {name} -> E={e:.1f}, N={n:.1f}")


def test_ljubljana_d96tm():
    """Test Ljubljana coordinates are in expected range."""
    e, n = wgs84_to_d96tm(*LJUBLJANA)
    # Ljubljana should be roughly E=461000-463000, N=100000-102000
    assert 460000 < e < 464000, f"Ljubljana easting out of range: {e}"
    assert 99000 < n < 103000, f"Ljubljana northing out of range: {n}"
    print(f"PASS: Ljubljana D96/TM = E={e:.1f}, N={n:.1f}")


def test_tile_coords():
    """Test tile coordinate calculation."""
    e, n = wgs84_to_d96tm(*LJUBLJANA)
    te, tn = get_tile_coords(e, n)
    print(f"PASS: Ljubljana tile = TM_{te}_{tn}")
    # Tile should be in reasonable range
    assert 400 < te < 600
    assert 50 < tn < 200


def test_tiles_for_radius():
    """Test tile list for a given radius."""
    tiles = get_tiles_for_radius(*LJUBLJANA, radius_m=500)
    print(f"PASS: Ljubljana r=500m needs {len(tiles)} tiles: {tiles}")
    # 500m radius from center -> at most 2x2 tiles (if near corner), usually 1-4
    assert 1 <= len(tiles) <= 4

    tiles_large = get_tiles_for_radius(*LJUBLJANA, radius_m=1500)
    print(f"PASS: Ljubljana r=1500m needs {len(tiles_large)} tiles: {tiles_large}")
    assert len(tiles_large) >= 4


def test_tile_filename():
    """Test tile filename generation."""
    assert tile_filename(462, 101) == "TM_462_101.laz"
    print("PASS: tile_filename")


if __name__ == "__main__":
    test_is_in_slovenia()
    test_wgs84_to_d96tm_roundtrip()
    test_ljubljana_d96tm()
    test_tile_coords()
    test_tiles_for_radius()
    test_tile_filename()
    print("\nAll tests passed!")
