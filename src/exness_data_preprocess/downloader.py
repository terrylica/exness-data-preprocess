"""
HTTP download operations for Exness tick data.

Handles downloading monthly ZIP files from ticks.ex2archive.com with the correct URL pattern.
"""

import os
from pathlib import Path
from typing import Optional
from urllib.error import URLError
from urllib.request import urlretrieve


class ExnessDownloader:
    """
    Download Exness monthly ZIP files from ticks.ex2archive.com.

    Handles:
    - Correct URL pattern construction for both Raw_Spread and Standard variants
    - File existence checking to avoid re-downloading
    - Progress reporting with file sizes
    - Error handling for failed downloads

    Example:
        >>> downloader = ExnessDownloader(temp_dir=Path("~/temp"))
        >>> zip_path = downloader.download_zip(year=2024, month=9, pair="EURUSD", variant="Raw_Spread")
        >>> if zip_path:
        ...     print(f"Downloaded: {zip_path}")
    """

    def __init__(self, temp_dir: Path):
        """
        Initialize downloader.

        Args:
            temp_dir: Directory for storing downloaded ZIP files
        """
        self.temp_dir = temp_dir
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def download_zip(
        self,
        year: int,
        month: int,
        pair: str = "EURUSD",
        variant: str = "Raw_Spread",
        force: bool = False,
    ) -> Optional[Path]:
        """
        Download Exness ZIP file for specific month and variant.

        Args:
            year: Year (e.g., 2024)
            month: Month (1-12)
            pair: Currency pair (default: EURUSD)
            variant: Data variant ("Raw_Spread" or "" for Standard)
            force: Re-download even if the ZIP is already on disk

        Returns:
            Path to downloaded ZIP file, or None if download failed

        Example:
            >>> downloader = ExnessDownloader(temp_dir=Path("~/temp"))
            >>> raw_zip = downloader.download_zip(2024, 9, variant="Raw_Spread")
            >>> std_zip = downloader.download_zip(2024, 9, variant="")
        """
        # Construct symbol name
        symbol = f"{pair}_{variant}" if variant else pair

        # Correct URL pattern: /ticks/{symbol}/{year}/{month}/
        url = f"https://ticks.ex2archive.com/ticks/{symbol}/{year}/{month:02d}/Exness_{symbol}_{year}_{month:02d}.zip"
        zip_path = self.temp_dir / f"Exness_{symbol}_{year}_{month:02d}.zip"

        if zip_path.exists():
            if not force:
                return zip_path
            zip_path.unlink()  # force: fetch the archive again instead of reusing a cached copy

        # Download to a sibling .part file and rename on success, so an interrupted or concurrent
        # download never leaves a truncated ZIP at zip_path for the exists() check above to reuse.
        part_path = zip_path.with_name(f"{zip_path.name}.{os.getpid()}.part")
        try:
            print(f"Downloading: {url}")
            urlretrieve(url, part_path)
            part_path.replace(zip_path)
            size_mb = zip_path.stat().st_size / 1024 / 1024
            print(f"✓ Downloaded: {size_mb:.2f} MB")
            return zip_path
        except URLError as e:
            print(f"✗ Download failed: {e}")
            return None
        finally:
            part_path.unlink(missing_ok=True)
