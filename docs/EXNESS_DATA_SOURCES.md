# Exness Data Sources - Complete Guide

**Source**: https://ticks.ex2archive.com/
**Last Updated**: 2025-10-12
**Related**: [`/tmp/exness-duckdb-test/EXNESS_VARIANTS.md`](/tmp/exness-duckdb-test/EXNESS_VARIANTS.md) (test artifacts)

---

## Quick Reference

### Phase7 Dual-Variant Downloads

```bash
# Primary: Raw_Spread (execution prices, 98% zero-spreads)
curl -L "https://ticks.ex2archive.com/ticks/EURUSD_Raw_Spread/2024/09/Exness_EURUSD_Raw_Spread_2024_09.zip" \
  -o Exness_EURUSD_Raw_Spread_2024_09.zip

# Reference: Standard (traditional quotes, always Bid < Ask)
curl -L "https://ticks.ex2archive.com/ticks/EURUSD/2024/09/Exness_EURUSD_2024_09.zip" \
  -o Exness_EURUSD_2024_09.zip
```

### URL Pattern

```
https://ticks.ex2archive.com/ticks/{VARIANT}/{YEAR}/{MONTH}/Exness_{VARIANT}_{YEAR}_{MONTH}.zip
```

**Examples**:
- Standard: `https://ticks.ex2archive.com/ticks/EURUSD/2024/09/Exness_EURUSD_2024_09.zip`
- Raw_Spread: `https://ticks.ex2archive.com/ticks/EURUSD_Raw_Spread/2024/09/Exness_EURUSD_Raw_Spread_2024_09.zip`

---

## Available Variants

Exness provides **4 main variants** of tick data for each instrument:

### 1. Standard (Default)
**Symbol**: `{INSTRUMENT}` (e.g., `EURUSD`)

**Characteristics**:
- **Zero-spreads**: 0% (always Bid < Ask)
- **Mean spread**: 0.7 pips (EURUSD)
- **Use case**: Reference quotes, position ratio calculation

**Example (EURUSD Sep 2024)**:
- Ticks: 1,082,145
- File size: 7.17 MB (compressed)
- CSV size: 66 MB (uncompressed)

### 2. Raw_Spread
**Symbol**: `{INSTRUMENT}_Raw_Spread` (e.g., `EURUSD_Raw_Spread`)

**Characteristics**:
- **Zero-spreads**: 97.81% (Bid == Ask)
- **Mean spread**: 0.0 pips
- **Use case**: Execution prices, zero-spread deviation analysis, OHLC construction

**Example (EURUSD Sep 2024)**:
- Ticks: 925,780
- File size: 5.88 MB (compressed)
- CSV size: 53 MB (uncompressed)

**Critical for Phase7**: Primary data source for BID-only OHLC construction

### 3. Standart_Plus (Note: Typo in Name)
**Symbol**: `{INSTRUMENT}_Standart_Plus` (e.g., `EURUSD_Standart_Plus`)

**Characteristics**:
- **Zero-spreads**: 0% (always Bid < Ask)
- **Mean spread**: 1.2 pips (70% wider than Standard)
- **Use case**: Wider spread variant, possibly retail accounts

**Example (EURUSD Sep 2024)**:
- Ticks: ~1,100,000 (estimated)
- File size: 7.51 MB (compressed)
- CSV size: 69 MB (uncompressed)

### 4. Zero_Spread
**Symbol**: `{INSTRUMENT}_Zero_Spread` (e.g., `EURUSD_Zero_Spread`)

**Characteristics**:
- **Zero-spreads**: 97.81% (Bid == Ask)
- **Mean spread**: 0.0 pips
- **Use case**: Nearly identical to Raw_Spread

**Example (EURUSD Sep 2024)**:
- Ticks: ~925,000 (estimated)
- File size: 5.90 MB (compressed)
- CSV size: 53 MB (uncompressed)

**Note**: Raw_Spread and Zero_Spread have nearly identical characteristics

### Additional Variants

- **{SYMBOL}m** - Micro lots variant (e.g., `EURUSDm`)
- **{SYMBOL}c** - Cent account variant (e.g., `EURUSDc`)

---

## Comparison Matrix (EURUSD Sep 2024)

| Variant | Ticks | Zero-Spreads | Mean Spread | File Size | Use Case |
|---------|-------|--------------|-------------|-----------|----------|
| **EURUSD** | 1.08M | 0% | 0.7 pips | 7.17 MB | Reference quotes |
| **EURUSD_Raw_Spread** | 925K | 97.81% | 0.0 pips | 5.88 MB | **Primary for phase7** |
| **EURUSD_Standart_Plus** | 1.10M | 0% | 1.2 pips | 7.51 MB | Wider spreads |
| **EURUSD_Zero_Spread** | 925K | 97.81% | 0.0 pips | 5.90 MB | Similar to Raw_Spread |

---

## CSV Format

All variants use identical CSV structure:

```csv
"Exness","Symbol","Timestamp","Bid","Ask"
"exness","EURUSD","2024-09-01 21:05:21.983Z",1.10477,1.10519
"exness","EURUSD","2024-09-01 21:05:26.080Z",1.10466,1.10508
...
```

**Columns**:
- `Exness` - Provider name (header: "Exness", data: "exness")
- `Symbol` - Instrument symbol
- `Timestamp` - ISO 8601 with milliseconds, UTC timezone
- `Bid` - Bid price (float)
- `Ask` - Ask price (float)

---

## Discovery & Automation

### List All Instruments

```bash
# Get all available instruments and variants
curl -s "https://ticks.ex2archive.com/ticks/" | jq -r '.[] | .name' | sort

# Filter for specific instrument
curl -s "https://ticks.ex2archive.com/ticks/" | jq -r '.[] | .name' | grep -i "EURUSD"
```

**Output** (EURUSD example):
```
EURUSD
EURUSD_Raw_Spread
EURUSD_Standart_Plus
EURUSD_Zero_Spread
EURUSDc
EURUSDc_Standart_Plus
EURUSDm
```

### Browse Available Months

```bash
# List years for EURUSD
curl -s "https://ticks.ex2archive.com/ticks/EURUSD/" | jq

# List months for EURUSD 2024
curl -s "https://ticks.ex2archive.com/ticks/EURUSD/2024/" | jq
```

---

## Download Scripts

### Helper Script

Located at: [`/tmp/exness-duckdb-test/download_exness_variants.sh`](/tmp/exness-duckdb-test/download_exness_variants.sh)

**Usage**:
```bash
# Download standard variant
./download_exness_variants.sh EURUSD 2024 09

# Download Raw_Spread variant
./download_exness_variants.sh EURUSD 2024 09 Raw_Spread

# Download Standart_Plus variant
./download_exness_variants.sh EURUSD 2024 09 Standart_Plus

# Download Zero_Spread variant
./download_exness_variants.sh EURUSD 2024 09 Zero_Spread
```

### Batch Download (All Variants)

```bash
#!/bin/bash
PAIR="EURUSD"
YEAR=2024
MONTH=09

variants=("EURUSD" "EURUSD_Raw_Spread" "EURUSD_Standart_Plus" "EURUSD_Zero_Spread")

for variant in "${variants[@]}"; do
    url="https://ticks.ex2archive.com/ticks/${variant}/${YEAR}/${MONTH}/Exness_${variant}_${YEAR}_${MONTH}.zip"
    curl -L "$url" -o "Exness_${variant}_${YEAR}_${MONTH}.zip"
done
```

### Python Download Function

```python
import requests
from pathlib import Path

def download_exness_variant(pair: str, year: int, month: int, variant: str = "") -> Path:
    """
    Download Exness tick data for specific variant.

    Args:
        pair: e.g., "EURUSD"
        year: e.g., 2024
        month: e.g., 9
        variant: "", "Raw_Spread", "Standart_Plus", "Zero_Spread"

    Returns:
        Path to downloaded ZIP file
    """
    symbol = f"{pair}_{variant}" if variant else pair
    url = f"https://ticks.ex2archive.com/ticks/{symbol}/{year}/{month:02d}/Exness_{symbol}_{year}_{month:02d}.zip"
    output = Path(f"Exness_{symbol}_{year}_{month:02d}.zip")

    print(f"Downloading {symbol} for {year}-{month:02d}...")
    response = requests.get(url, stream=True)
    response.raise_for_status()

    with open(output, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)

    print(f"✅ Downloaded: {output} ({output.stat().st_size / 1024 / 1024:.2f} MB)")
    return output

# Example: Phase7 dual-variant download
raw_spread = download_exness_variant("EURUSD", 2024, 9, "Raw_Spread")
standard = download_exness_variant("EURUSD", 2024, 9)
```

---

## Phase7 Methodology Requirements

### Dual-Variant Approach

Phase7 BID-only OHLC construction requires **2 variants**:

1. **Primary: Raw_Spread**
   - Source for BID prices (OHLC construction)
   - Contains zero-spread events (Bid == Ask)
   - Used for deviation detection

2. **Reference: Standard**
   - Traditional bid/ask quotes
   - Used for position ratio calculation
   - ASOF merge with Raw_Spread (1-second tolerance)

### Position Ratio Formula

```python
position_ratio = (raw_mid - std_bid) / (std_ask - std_bid)
```

Where:
- `raw_mid = (raw_bid + raw_ask) / 2` from Raw_Spread variant
- `std_bid`, `std_ask` from Standard variant (ASOF merged)

**Interpretation**:
- `position_ratio = 0.5` → Execution at midpoint (no deviation)
- `position_ratio < 0.5` → Bid-biased execution
- `position_ratio > 0.5` → Ask-biased execution
- `|position_ratio - 0.5| > 0.05` → Deviation threshold

### 9-Column OHLC Schema

```sql
Timestamp               TIMESTAMP WITH TIME ZONE  -- Minute-aligned
Open                    DOUBLE                    -- Raw_Spread BID first
High                    DOUBLE                    -- Raw_Spread BID max
Low                     DOUBLE                    -- Raw_Spread BID min
Close                   DOUBLE                    -- Raw_Spread BID last
raw_spread_avg          DOUBLE                    -- AVG(Ask-Bid) from Raw_Spread
standard_spread_avg     DOUBLE                    -- AVG(Ask-Bid) from Standard
tick_count_raw_spread   BIGINT                    -- COUNT(*) from Raw_Spread
tick_count_standard     BIGINT                    -- COUNT(*) from Standard
```

**Full Specification**: [`docs/research/eurusd-zero-spread-deviations/data/plan/phase7_bid_ohlc_construction_v1.1.0.md`](research/eurusd-zero-spread-deviations/data/plan/phase7_bid_ohlc_construction_v1.1.0.md)

---

## Data Quality Characteristics

### Timestamp Precision

- **Millisecond precision**: ISO 8601 format (e.g., `2024-09-01 21:05:21.983Z`)
- **Irregular intervals**: Variable tick frequency (1µs to 130.61s)
- **Trading hours**: 24/7 forex, weekend gaps expected
- **Timezone**: UTC (Z suffix)

### Spread Behavior

**Standard Variant**:
- **Minimum spread**: 0.6 pips (EURUSD)
- **Mean spread**: 0.7 pips (EURUSD)
- **Never zero**: Always `Bid < Ask`

**Raw_Spread Variant**:
- **Zero-spreads**: 97.81% of ticks (EURUSD)
- **Mean spread**: 0.0 pips
- **Represents execution**: Bid == Ask at most ticks

### Temporal Coverage

- **Availability**: 2020-2025+ (continuous)
- **Monthly files**: One ZIP per month
- **Trading days**: ~21 days per month (forex weekdays)
- **Tick density**: ~2M ticks per month (EURUSD)

---

## Storage Estimates

### Single Instrument (EURUSD)

**Per Month** (21 trading days):
- Raw_Spread ticks: 925K ticks
- Standard ticks: 1.08M ticks
- **Unified DuckDB**: 11.26 MB (ticks + OHLC bars)

**Annual** (12 months):
- 12 × 11.5 MB = **~138 MB/year**

**5-Year History**:
- 5 × 138 MB = **~690 MB**

### Multi-Instrument

**Two Instruments** (EURUSD + XAUUSD):
- Annual: 2 × 138 MB = **~276 MB/year**
- 5-year: 2 × 690 MB = **~1.38 GB**

**Storage is extremely manageable** for modern systems.

---

## References

### Official Sources

- **Exness Tick History**: https://www.exness.com/tick-history/ (Cloudflare protected)
- **ex2archive.com**: https://ticks.ex2archive.com/ (direct access, JSON listings)

### Related Documentation

- **Unified DuckDB Validation**: [`/tmp/exness-duckdb-test/FINDINGS.md`](/tmp/exness-duckdb-test/FINDINGS.md)
- **Variant Analysis**: [`/tmp/exness-duckdb-test/EXNESS_VARIANTS.md`](/tmp/exness-duckdb-test/EXNESS_VARIANTS.md)
- **Phase7 Methodology**: [`docs/research/eurusd-zero-spread-deviations/01-methodology.md`](research/eurusd-zero-spread-deviations/01-methodology.md)
- **Zero-Spread Research**: [`docs/research/eurusd-zero-spread-deviations/README.md`](research/eurusd-zero-spread-deviations/README.md)

### Implementation

- **Current Processor**: [`src/exness_data_preprocess/processor.py`](../src/exness_data_preprocess/processor.py) (needs refactoring)
- **Test Script**: [`/tmp/exness-duckdb-test/test_real_unified.py`](/tmp/exness-duckdb-test/test_real_unified.py)
- **Download Helper**: [`/tmp/exness-duckdb-test/download_exness_variants.sh`](/tmp/exness-duckdb-test/download_exness_variants.sh)

---

**Last Updated**: 2025-10-12
**Next Steps**: Refactor `ExnessDataProcessor` to implement dual-variant downloads and unified DuckDB storage
