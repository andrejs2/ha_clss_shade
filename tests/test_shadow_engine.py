"""Tests for shadow_engine.py — sun position and shadow computation."""

from __future__ import annotations

import asyncio
import sys
import time
import tempfile
from datetime import datetime, timezone, date
from pathlib import Path

import numpy as np

sys.path.insert(0, "custom_components")

from ha_clss_shade.shadow_engine import (
    SunPosition,
    compute_shadow_map,
    compute_sun_position,
    compute_daily_sun_hours,
    get_seasonal_transmittance,
    _build_transmittance_grid,
    CLASS_HIGH_VEG,
    CLASS_BUILDING,
)
from ha_clss_shade.clss_data.rasterizer import SiteModel

LJUBLJANA = (46.0489, 14.5087)


def test_sun_position_noon():
    """Sun should be roughly south at noon in Slovenia."""
    dt = datetime(2026, 6, 21, 12, 0, 0, tzinfo=timezone.utc)  # Summer solstice ~noon UTC
    sun = compute_sun_position(*LJUBLJANA, dt)
    # At noon UTC in Slovenia (UTC+2 = 14:00 local), sun should be roughly south (160-200°)
    assert 140 < sun.azimuth < 220, f"Noon azimuth: {sun.azimuth:.1f}°"
    # Summer solstice at 46°N, elevation should be ~67° at solar noon
    assert sun.elevation > 40, f"Noon elevation too low: {sun.elevation:.1f}°"
    assert sun.is_above_horizon
    print(f"PASS: noon sun az={sun.azimuth:.1f}° elev={sun.elevation:.1f}°")


def test_sun_position_night():
    """Sun should be below horizon at midnight."""
    dt = datetime(2026, 6, 21, 0, 0, 0, tzinfo=timezone.utc)
    sun = compute_sun_position(*LJUBLJANA, dt)
    # At midnight UTC (2:00 local) sun should be below horizon
    assert sun.elevation < 0, f"Midnight elevation: {sun.elevation:.1f}°"
    assert not sun.is_above_horizon
    print(f"PASS: midnight sun elev={sun.elevation:.1f}° (below horizon)")


def test_sun_position_sunrise():
    """Sun should be near horizon at sunrise (~5:15 UTC in June Ljubljana)."""
    dt = datetime(2026, 6, 21, 3, 15, 0, tzinfo=timezone.utc)  # ~5:15 local
    sun = compute_sun_position(*LJUBLJANA, dt)
    # Should be near horizon, roughly NE
    assert -5 < sun.elevation < 15, f"Sunrise elevation: {sun.elevation:.1f}°"
    assert 30 < sun.azimuth < 90, f"Sunrise azimuth: {sun.azimuth:.1f}°"
    print(f"PASS: sunrise sun az={sun.azimuth:.1f}° elev={sun.elevation:.1f}°")


def test_sun_position_winter():
    """Winter sun should be lower than summer."""
    summer = compute_sun_position(*LJUBLJANA, datetime(2026, 6, 21, 11, 0, tzinfo=timezone.utc))
    winter = compute_sun_position(*LJUBLJANA, datetime(2026, 12, 21, 11, 0, tzinfo=timezone.utc))
    assert summer.elevation > winter.elevation + 30, (
        f"Summer {summer.elevation:.1f}° should be much higher than winter {winter.elevation:.1f}°"
    )
    print(f"PASS: summer elev={summer.elevation:.1f}° > winter elev={winter.elevation:.1f}°")


def test_seasonal_transmittance():
    """Test seasonal variation for high vegetation."""
    summer = get_seasonal_transmittance(CLASS_HIGH_VEG, 7)
    spring = get_seasonal_transmittance(CLASS_HIGH_VEG, 4)
    winter = get_seasonal_transmittance(CLASS_HIGH_VEG, 1)
    assert summer < spring < winter, f"Expected summer<spring<winter: {summer},{spring},{winter}"
    assert get_seasonal_transmittance(CLASS_BUILDING, 7) == 0.0
    print(f"PASS: transmittance summer={summer} spring={spring} winter={winter}")


def test_shadow_flat_terrain():
    """On perfectly flat terrain with no objects, there should be no shadow."""
    n = 100
    site = SiteModel(
        dsm=np.full((n, n), 300.0, dtype=np.float32),
        dtm=np.full((n, n), 300.0, dtype=np.float32),
        classification=np.full((n, n), 2, dtype=np.uint8),  # all ground
        resolution=1.0,
        origin_e=461000.0, origin_n=100500.0,
        center_e=461050.0, center_n=100550.0,
    )
    sun = SunPosition(azimuth=180.0, elevation=45.0)
    result = compute_shadow_map(site, sun, date(2026, 6, 21))
    assert np.all(result.shadow_map == 0.0), "Flat terrain should have no shadow"
    print("PASS: flat terrain = no shadow")


def test_shadow_single_building():
    """A tall building should cast a shadow on the north side (sun from south)."""
    n = 100
    dsm = np.full((n, n), 300.0, dtype=np.float32)
    dtm = np.full((n, n), 300.0, dtype=np.float32)
    cls = np.full((n, n), 2, dtype=np.uint8)

    # Place a 20m tall building at center
    dsm[48:52, 48:52] = 320.0
    cls[48:52, 48:52] = 6  # building

    site = SiteModel(
        dsm=dsm, dtm=dtm, classification=cls,
        resolution=1.0,
        origin_e=461000.0, origin_n=100500.0,
        center_e=461050.0, center_n=100550.0,
    )

    # Sun from south (azimuth=180), 30° elevation
    # Shadow falls north = higher row indices (row 0 = south in our grid)
    sun = SunPosition(azimuth=180.0, elevation=30.0)
    result = compute_shadow_map(site, sun, date(2026, 6, 21))

    # South of building (rows 20-48) = sun side, no shadow
    shadow_south = result.shadow_map[20:48, 48:52]
    # North of building (rows 52-80) = shadow side
    shadow_north = result.shadow_map[52:80, 48:52]

    assert np.mean(shadow_south) < 0.1, f"South (sun side) shadow too high: {np.mean(shadow_south):.2f}"
    assert np.mean(shadow_north) > 0.5, f"North (shade side) shadow too low: {np.mean(shadow_north):.2f}"
    print(f"PASS: building shadow south(sun)={np.mean(shadow_south):.2f} north(shade)={np.mean(shadow_north):.2f}")


def test_shadow_below_horizon():
    """When sun is below horizon, everything should be in shadow."""
    n = 50
    site = SiteModel(
        dsm=np.full((n, n), 300.0, dtype=np.float32),
        dtm=np.full((n, n), 300.0, dtype=np.float32),
        classification=np.full((n, n), 2, dtype=np.uint8),
        resolution=1.0,
        origin_e=0.0, origin_n=0.0, center_e=25.0, center_n=25.0,
    )
    sun = SunPosition(azimuth=180.0, elevation=-10.0)
    result = compute_shadow_map(site, sun, date(2026, 6, 21))
    assert np.all(result.shadow_map == 1.0), "Below horizon = full shadow"
    print("PASS: below horizon = full shadow")


def test_zone_shade_percent():
    """Test zone-based shade calculation."""
    n = 50
    shadow_map = np.zeros((n, n), dtype=np.float32)
    shadow_map[0:25, :] = 1.0  # top half in shadow

    site = SiteModel(
        dsm=np.zeros((n, n), dtype=np.float32),
        dtm=np.zeros((n, n), dtype=np.float32),
        classification=np.zeros((n, n), dtype=np.uint8),
        resolution=1.0,
        origin_e=0.0, origin_n=0.0, center_e=25.0, center_n=25.0,
    )
    from ha_clss_shade.shadow_engine import ShadowResult
    result = ShadowResult(
        shadow_map=shadow_map, sun=SunPosition(180, 45),
        site=site, timestamp=datetime.now(),
    )

    full_mask = np.ones((n, n), dtype=bool)
    assert abs(result.zone_shade_percent(full_mask) - 50.0) < 0.1
    print("PASS: zone shade percent")


def test_shadow_performance():
    """Benchmark shadow computation on a realistic grid size."""
    n = 800  # matches our real Ljubljana rasterization
    dsm = np.random.uniform(290, 350, (n, n)).astype(np.float32)
    dtm = np.full((n, n), 300.0, dtype=np.float32)
    cls = np.random.choice([2, 3, 5, 6], (n, n), p=[0.4, 0.1, 0.3, 0.2]).astype(np.uint8)

    site = SiteModel(
        dsm=dsm, dtm=dtm, classification=cls,
        resolution=0.5,
        origin_e=461000.0, origin_n=100500.0,
        center_e=461200.0, center_n=100700.0,
    )

    sun = SunPosition(azimuth=200.0, elevation=45.0)
    start = time.time()
    result = compute_shadow_map(site, sun, date(2026, 6, 21))
    elapsed = time.time() - start
    print(f"PASS: performance {n}x{n} grid in {elapsed:.2f}s, mean shade={np.mean(result.shadow_map)*100:.1f}%")


async def test_shadow_real_tile():
    """Test shadow computation with real Ljubljana data."""
    from ha_clss_shade.clss_data.slovenian_downloader import ArsoLidarDownloader
    from ha_clss_shade.clss_data.rasterizer import rasterize_laz

    with tempfile.TemporaryDirectory() as tmpdir:
        cache = Path(tmpdir)
        dl = ArsoLidarDownloader(cache_dir=cache)
        try:
            paths = await dl.download_location(*LJUBLJANA)
        finally:
            await dl.close()

        site = rasterize_laz(paths, *LJUBLJANA, radius_m=200.0)

        # Summer noon shadow
        dt = datetime(2026, 6, 21, 11, 0, 0, tzinfo=timezone.utc)
        sun = compute_sun_position(*LJUBLJANA, dt)
        print(f"Sun: az={sun.azimuth:.1f}° elev={sun.elevation:.1f}°")

        start = time.time()
        result = compute_shadow_map(site, sun, dt.date())
        elapsed = time.time() - start

        print(f"Shadow computation: {elapsed:.2f}s")
        print(f"Mean shade: {np.mean(result.shadow_map)*100:.1f}%")
        print(f"Full sun cells: {np.mean(result.shadow_map == 0)*100:.1f}%")
        print(f"Full shade cells: {np.mean(result.shadow_map >= 0.99)*100:.1f}%")

        # Ljubljana at noon in summer should have moderate shadow (buildings + trees)
        mean_shade = np.mean(result.shadow_map)
        assert 0.05 < mean_shade < 0.8, f"Mean shade out of range: {mean_shade:.2f}"
        print(f"PASS: real tile shadow computation")


if __name__ == "__main__":
    test_sun_position_noon()
    test_sun_position_night()
    test_sun_position_sunrise()
    test_sun_position_winter()
    test_seasonal_transmittance()
    test_shadow_flat_terrain()
    test_shadow_single_building()
    test_shadow_below_horizon()
    test_zone_shade_percent()
    test_shadow_performance()

    if "--full" in sys.argv:
        print("\n--- Running real tile shadow test ---")
        asyncio.run(test_shadow_real_tile())

    print("\nAll tests passed!")
