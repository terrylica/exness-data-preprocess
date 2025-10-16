"""
ZIP file parsing and DataFrame creation for tick data.

Handles loading CSV tick data from Exness ZIP files into pandas DataFrames with proper typing
and timezone handling.
"""

import zipfile
from pathlib import Path

import pandas as pd


class TickLoader:
    """
    Load tick data from Exness ZIP files.

    Handles:
    - ZIP file extraction without writing temporary files
    - CSV parsing with proper column selection
    - Timestamp parsing and UTC timezone conversion
    - Type safety (Timestamp, Bid, Ask columns)

    Example:
        >>> from pathlib import Path
        >>> loader = TickLoader()
        >>> df = loader.load_from_zip(Path("Exness_EURUSD_Raw_Spread_2024_09.zip"))
        >>> print(df.columns)
        Index(['Timestamp', 'Bid', 'Ask'], dtype='object')
        >>> print(df.dtypes)
        Timestamp    datetime64[ns, UTC]
        Bid                      float64
        Ask                      float64
    """

    @staticmethod
    def load_from_zip(zip_path: Path) -> pd.DataFrame:
        """
        Load ticks from ZIP file into DataFrame.

        Args:
            zip_path: Path to Exness ZIP file containing CSV tick data

        Returns:
            DataFrame with columns: Timestamp (UTC), Bid, Ask

        Raises:
            FileNotFoundError: If ZIP file does not exist
            zipfile.BadZipFile: If file is not a valid ZIP
            KeyError: If expected CSV file not found in ZIP

        Example:
            >>> loader = TickLoader()
            >>> df = loader.load_from_zip(Path("~/temp/Exness_EURUSD_Raw_Spread_2024_09.zip"))
            >>> print(f"Loaded {len(df):,} ticks")
            Loaded 925,123 ticks
        """
        with zipfile.ZipFile(zip_path, "r") as zf:
            csv_name = zip_path.stem + ".csv"
            with zf.open(csv_name) as csv_file:
                df = pd.read_csv(
                    csv_file, usecols=["Timestamp", "Bid", "Ask"], parse_dates=["Timestamp"]
                )

        # Convert to UTC timezone-aware
        df["Timestamp"] = pd.to_datetime(df["Timestamp"], utc=True)
        return df
