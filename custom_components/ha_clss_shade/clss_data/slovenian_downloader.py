"""Download Slovenian CLSS/LSS LiDAR tiles from ARSO server."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

import aiohttp

from .geo import (
    get_tile_coords,
    is_in_slovenia,
    tile_filename,
    wgs84_to_d96tm,
)

_LOGGER = logging.getLogger(__name__)

ARSO_LIDAR_BASE = "http://gis.arso.gov.si/lidar"
ARSO_PRODUCT_PATH = "GKOT/laz"
ARSO_CRS_DIR = "D96TM"

# Known block range on ARSO server (LSS data)
BLOCK_MIN = 1
BLOCK_MAX = 60

# Probe concurrency — don't hammer the server
PROBE_CONCURRENCY = 5
DOWNLOAD_TIMEOUT = 300  # seconds


class TileNotFoundError(Exception):
    """Raised when a tile cannot be found on the ARSO server."""


class DownloadError(Exception):
    """Raised when a tile download fails."""


def _tile_url(block: int, tile_e: int, tile_n: int) -> str:
    """Build ARSO download URL for a tile."""
    fname = tile_filename(tile_e, tile_n)
    return f"{ARSO_LIDAR_BASE}/{ARSO_PRODUCT_PATH}/b_{block}/{ARSO_CRS_DIR}/{fname}"


class ArsoLidarDownloader:
    """Downloads LiDAR LAZ tiles from the ARSO server.

    Handles block number discovery via HTTP HEAD probing and caches
    the block mapping to avoid repeated probes.
    """

    def __init__(
        self,
        cache_dir: Path,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        self._cache_dir = cache_dir
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._session = session
        self._owns_session = session is None
        self._block_cache: dict[str, int] = {}
        self._block_cache_file = cache_dir / "block_cache.json"
        self._load_block_cache()

    def _load_block_cache(self) -> None:
        """Load cached block mappings from disk."""
        if self._block_cache_file.exists():
            try:
                self._block_cache = json.loads(self._block_cache_file.read_text())
                _LOGGER.debug("Loaded block cache with %d entries", len(self._block_cache))
            except (json.JSONDecodeError, OSError):
                self._block_cache = {}

    async def _save_block_cache(self) -> None:
        """Persist block cache to disk (async-safe)."""
        try:
            data = json.dumps(self._block_cache, indent=2)
            await asyncio.get_event_loop().run_in_executor(
                None, self._block_cache_file.write_text, data
            )
        except OSError as err:
            _LOGGER.warning("Failed to save block cache: %s", err)

    @staticmethod
    def _tile_key(tile_e: int, tile_n: int) -> str:
        return f"{tile_e}_{tile_n}"

    async def _ensure_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
            self._owns_session = True
        return self._session

    async def close(self) -> None:
        """Close the HTTP session if we own it."""
        if self._owns_session and self._session and not self._session.closed:
            await self._session.close()

    async def find_block(self, tile_e: int, tile_n: int) -> int:
        """Find the block number for a tile via HEAD probing.

        Checks the cache first. If not found, probes the ARSO server
        with concurrent HEAD requests across the block range.

        Returns:
            Block number.

        Raises:
            TileNotFoundError: If the tile doesn't exist on the server.
        """
        key = self._tile_key(tile_e, tile_n)
        if key in self._block_cache:
            return self._block_cache[key]

        session = await self._ensure_session()
        fname = tile_filename(tile_e, tile_n)
        _LOGGER.info("Probing ARSO server for tile %s block number...", fname)

        semaphore = asyncio.Semaphore(PROBE_CONCURRENCY)
        found_block: int | None = None

        async def probe(block: int) -> None:
            nonlocal found_block
            if found_block is not None:
                return
            async with semaphore:
                if found_block is not None:
                    return
                url = _tile_url(block, tile_e, tile_n)
                try:
                    async with session.head(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                        if resp.status == 200:
                            found_block = block
                except (aiohttp.ClientError, asyncio.TimeoutError):
                    pass

        tasks = [probe(b) for b in range(BLOCK_MIN, BLOCK_MAX + 1)]
        await asyncio.gather(*tasks)

        if found_block is None:
            raise TileNotFoundError(
                f"Tile {fname} not found on ARSO server (probed blocks {BLOCK_MIN}-{BLOCK_MAX})"
            )

        self._block_cache[key] = found_block
        await self._save_block_cache()
        _LOGGER.info("Tile %s found in block b_%d", fname, found_block)
        return found_block

    async def download_tile(
        self, tile_e: int, tile_n: int, force: bool = False
    ) -> Path:
        """Download a single LAZ tile.

        Args:
            tile_e: Tile easting coordinate.
            tile_n: Tile northing coordinate.
            force: Re-download even if cached.

        Returns:
            Path to the downloaded LAZ file.
        """
        fname = tile_filename(tile_e, tile_n)
        local_path = self._cache_dir / fname

        if local_path.exists() and not force:
            _LOGGER.debug("Tile %s already cached at %s", fname, local_path)
            return local_path

        block = await self.find_block(tile_e, tile_n)
        url = _tile_url(block, tile_e, tile_n)
        session = await self._ensure_session()

        _LOGGER.info("Downloading %s from %s", fname, url)
        try:
            timeout = aiohttp.ClientTimeout(total=DOWNLOAD_TIMEOUT)
            async with session.get(url, timeout=timeout) as resp:
                if resp.status != 200:
                    raise DownloadError(f"HTTP {resp.status} for {url}")

                total = resp.content_length or 0
                downloaded = 0
                tmp_path = local_path.with_suffix(".laz.tmp")

                # Read all chunks into memory, then write in executor
                chunks: list[bytes] = []
                async for chunk in resp.content.iter_chunked(1024 * 256):
                    chunks.append(chunk)
                    downloaded += len(chunk)
                    if total > 0:
                        pct = downloaded / total * 100
                        _LOGGER.debug("Downloading %s: %.1f%%", fname, pct)

                data = b"".join(chunks)

                def _write_file() -> None:
                    tmp_path.write_bytes(data)
                    tmp_path.rename(local_path)

                await asyncio.get_event_loop().run_in_executor(None, _write_file)
                size_mb = local_path.stat().st_size / (1024 * 1024)
                _LOGGER.info("Downloaded %s (%.1f MB)", fname, size_mb)
                return local_path

        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise DownloadError(f"Failed to download {fname}: {err}") from err

    async def download_location(
        self,
        lat: float,
        lon: float,
        include_neighbors: bool = False,
        force: bool = False,
    ) -> list[Path]:
        """Download LiDAR tile(s) for a location.

        By default downloads only the single 1 km² tile containing the
        location (~30-50 MB). This covers the home + immediate surroundings
        which is sufficient for most shade analysis.

        Args:
            lat: Center latitude (WGS84).
            lon: Center longitude (WGS84).
            include_neighbors: Also download 8 surrounding tiles (3x3 km²).
                Use only when the location is near a tile edge or when
                tall structures on neighboring tiles cast shadows.
            force: Re-download even if cached.

        Returns:
            List of paths to downloaded LAZ files.

        Raises:
            ValueError: If location is outside Slovenia.
        """
        if not is_in_slovenia(lat, lon):
            raise ValueError(
                f"Location ({lat}, {lon}) is outside Slovenia "
                f"(lat {SI_LAT_MIN}-{SI_LAT_MAX}, lon {SI_LON_MIN}-{SI_LON_MAX})"
            )

        easting, northing = wgs84_to_d96tm(lat, lon)
        center_e, center_n = get_tile_coords(easting, northing)

        if include_neighbors:
            tiles = [
                (center_e + de, center_n + dn)
                for de in (-1, 0, 1)
                for dn in (-1, 0, 1)
            ]
        else:
            tiles = [(center_e, center_n)]

        _LOGGER.info(
            "Downloading %d tile(s) for (%.4f, %.4f) / D96TM (%.1f, %.1f)",
            len(tiles), lat, lon, easting, northing,
        )

        paths = []
        errors = []
        for tile_e, tile_n in tiles:
            try:
                path = await self.download_tile(tile_e, tile_n, force=force)
                paths.append(path)
            except (TileNotFoundError, DownloadError) as err:
                _LOGGER.warning("Skipping tile TM_%d_%d: %s", tile_e, tile_n, err)
                errors.append((tile_e, tile_n, str(err)))

        if not paths:
            raise DownloadError(
                f"No tiles could be downloaded. Errors: {errors}"
            )

        _LOGGER.info(
            "Downloaded %d/%d tile(s) (%d errors)", len(paths), len(tiles), len(errors)
        )
        return paths

    def get_cached_tiles(self) -> list[Path]:
        """List all locally cached LAZ files."""
        return sorted(self._cache_dir.glob("TM_*.laz"))

    def get_manual_tiles(self) -> list[Path]:
        """List manually placed LAZ/LAS files in cache directory."""
        laz = list(self._cache_dir.glob("*.laz"))
        las = list(self._cache_dir.glob("*.las"))
        return sorted(laz + las)


