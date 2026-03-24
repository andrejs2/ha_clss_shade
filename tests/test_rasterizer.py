"""Tests for rasterizer.py — LAZ to numpy grid conversion.

Requires a real LAZ tile download (~48 MB). Run with --full flag.
Quick mode uses a synthetic point cloud.
"""

from __future__ import annotations

import asyncio
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, "custom_components")

from ha_clss_shade.clss_data.rasterizer import SiteModel, rasterize_laz, _auto_resolution

LJUBLJANA = (46.0489, 14.5087)


def test_auto_resolution():
    """Test auto resolution calculation."""
    # 10 pts/m2 over 500m radius -> ~7.85M points
    n = 7_850_000
    x = np.random.uniform(0, 1000, n)
    y = np.random.uniform(0, 1000, n)
    res = _auto_resolution(x, y, radius_m=500.0)
    # 10 pts/m2, target 4 pts/cell -> cell area = 0.4 m2 -> res ~0.63 -> snaps to 0.5
    assert 0.5 <= res <= 1.0, f"Resolution out of range: {res}"
    print(f"PASS: auto_resolution = {res}m (10 pts/m2, r=500m)")


def test_site_model_save_load():
    """Test save/load roundtrip."""
    model = SiteModel(
        dsm=np.random.rand(100, 100).astype(np.float32),
        dtm=np.random.rand(100, 100).astype(np.float32),
        classification=np.random.randint(0, 7, (100, 100), dtype=np.uint8),
        resolution=1.0,
        origin_e=461000.0,
        origin_n=100500.0,
        center_e=461500.0,
        center_n=101000.0,
    )
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "test_model.npz"
        model.save(path)
        loaded = SiteModel.load(path)

        assert np.allclose(model.dsm, loaded.dsm)
        assert np.allclose(model.dtm, loaded.dtm)
        assert np.array_equal(model.classification, loaded.classification)
        assert model.resolution == loaded.resolution
        assert model.origin_e == loaded.origin_e
        print(f"PASS: save/load roundtrip ({path.stat().st_size / 1024:.0f} KB)")


def test_height_above_ground():
    """Test normalized height computation."""
    model = SiteModel(
        dsm=np.array([[10.0, 20.0], [15.0, 25.0]], dtype=np.float32),
        dtm=np.array([[5.0, 5.0], [10.0, 10.0]], dtype=np.float32),
        classification=np.array([[2, 6], [3, 5]], dtype=np.uint8),
        resolution=1.0,
        origin_e=0.0, origin_n=0.0, center_e=1.0, center_n=1.0,
    )
    hag = model.height_above_ground
    expected = np.array([[5.0, 15.0], [5.0, 15.0]])
    assert np.allclose(hag, expected), f"Height above ground mismatch: {hag}"
    print("PASS: height_above_ground")


async def test_rasterize_real_tile():
    """Test rasterization with a real Ljubljana LAZ tile."""
    from ha_clss_shade.clss_data.slovenian_downloader import ArsoLidarDownloader

    with tempfile.TemporaryDirectory() as tmpdir:
        cache = Path(tmpdir)
        dl = ArsoLidarDownloader(cache_dir=cache)
        try:
            paths = await dl.download_location(*LJUBLJANA)
        finally:
            await dl.close()

        print(f"Downloaded: {[p.name for p in paths]}")

        # Rasterize with 200m radius (smaller = faster for testing)
        model = rasterize_laz(paths, *LJUBLJANA, radius_m=200.0)

        print(f"Grid: {model.rows}x{model.cols}, res={model.resolution}m")
        print(f"DSM range: {np.nanmin(model.dsm):.1f} - {np.nanmax(model.dsm):.1f} m")
        print(f"DTM range: {np.nanmin(model.dtm):.1f} - {np.nanmax(model.dtm):.1f} m")
        print(f"Height above ground range: {np.nanmin(model.height_above_ground):.1f} - {np.nanmax(model.height_above_ground):.1f} m")

        classes, counts = np.unique(model.classification, return_counts=True)
        for c, n in zip(classes, counts):
            print(f"  Class {c}: {n} cells ({n / model.classification.size * 100:.1f}%)")

        # Basic sanity checks
        assert model.rows > 10
        assert model.cols > 10
        assert model.resolution > 0
        assert np.nanmin(model.dsm) > 200  # Ljubljana is ~300m elevation
        assert np.nanmax(model.dsm) < 600
        assert np.any(model.classification == 6)  # Should have buildings (Ljubljana castle area)

        # Test save/load
        save_path = cache / "site_model.npz"
        model.save(save_path)
        loaded = SiteModel.load(save_path)
        assert np.allclose(model.dsm, loaded.dsm, equal_nan=True)
        print(f"PASS: real tile rasterization + save/load ({save_path.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    test_auto_resolution()
    test_site_model_save_load()
    test_height_above_ground()

    if "--full" in sys.argv:
        print("\n--- Running real tile test (download + rasterize) ---")
        asyncio.run(test_rasterize_real_tile())

    print("\nAll tests passed!")
