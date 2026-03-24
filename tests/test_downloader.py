"""Tests for slovenian_downloader.py — ARSO tile discovery and download."""

from __future__ import annotations

import asyncio
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, "custom_components")

from ha_clss_shade.clss_data.slovenian_downloader import ArsoLidarDownloader, TileNotFoundError


LJUBLJANA = (46.0489, 14.5087)


async def test_find_block_ljubljana():
    """Test block discovery for Ljubljana tile."""
    with tempfile.TemporaryDirectory() as tmpdir:
        dl = ArsoLidarDownloader(cache_dir=Path(tmpdir))
        try:
            # Ljubljana tile TM_461_101 should be in block 35
            block = await dl.find_block(461, 101)
            assert block == 35, f"Expected block 35, got {block}"
            print(f"PASS: Ljubljana TM_461_101 -> b_{block}")

            # Check cache was populated
            assert "461_101" in dl._block_cache
            print("PASS: Block cache populated")

            # Second call should use cache (instant)
            block2 = await dl.find_block(461, 101)
            assert block2 == 35
            print("PASS: Block cache hit")
        finally:
            await dl.close()


async def test_find_block_maribor():
    """Test block discovery for Maribor tile."""
    with tempfile.TemporaryDirectory() as tmpdir:
        dl = ArsoLidarDownloader(cache_dir=Path(tmpdir))
        try:
            block = await dl.find_block(549, 157)
            assert block == 26, f"Expected block 26, got {block}"
            print(f"PASS: Maribor TM_549_157 -> b_{block}")
        finally:
            await dl.close()


async def test_find_block_koper():
    """Test block discovery for Koper tile."""
    with tempfile.TemporaryDirectory() as tmpdir:
        dl = ArsoLidarDownloader(cache_dir=Path(tmpdir))
        try:
            block = await dl.find_block(400, 46)
            assert block == 21, f"Expected block 21, got {block}"
            print(f"PASS: Koper TM_400_46 -> b_{block}")
        finally:
            await dl.close()


async def test_download_tile():
    """Test actual tile download (single tile ~48 MB)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = Path(tmpdir)
        dl = ArsoLidarDownloader(cache_dir=cache)
        try:
            # Download Ljubljana center tile only
            paths = await dl.download_location(*LJUBLJANA)
            assert len(paths) == 1, f"Expected 1 tile, got {len(paths)}"
            size_mb = paths[0].stat().st_size / (1024 * 1024)
            assert size_mb > 1, f"File too small: {size_mb:.1f} MB"
            print(f"PASS: Downloaded {paths[0].name} ({size_mb:.1f} MB)")

            # Second download should be cached
            paths2 = await dl.download_location(*LJUBLJANA)
            assert paths[0] == paths2[0]
            print("PASS: Second download used cache")
        finally:
            await dl.close()


async def test_block_cache_persistence():
    """Test that block cache persists across instances."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = Path(tmpdir)

        # First instance: discover block
        dl1 = ArsoLidarDownloader(cache_dir=cache)
        try:
            await dl1.find_block(461, 101)
        finally:
            await dl1.close()

        # Second instance: should load from cache
        dl2 = ArsoLidarDownloader(cache_dir=cache)
        try:
            assert "461_101" in dl2._block_cache
            assert dl2._block_cache["461_101"] == 35
            print("PASS: Block cache persists across instances")
        finally:
            await dl2.close()


async def run_quick_tests():
    """Run only the fast tests (no large downloads)."""
    await test_find_block_ljubljana()
    await test_find_block_maribor()
    await test_find_block_koper()
    await test_block_cache_persistence()
    print("\nAll quick tests passed!")


async def run_all_tests():
    """Run all tests including download."""
    await run_quick_tests()
    print("\n--- Running download test (may take a while) ---")
    await test_download_tile()
    print("\nAll tests passed!")


if __name__ == "__main__":
    if "--full" in sys.argv:
        asyncio.run(run_all_tests())
    else:
        asyncio.run(run_quick_tests())
