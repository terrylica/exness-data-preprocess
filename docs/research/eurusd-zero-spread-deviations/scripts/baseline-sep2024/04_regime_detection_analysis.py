#!/usr/bin/env python3
"""
Regime Detection via Deviation Clustering
=========================================
Research Question: Do clusters of zero-spread deviations mark regime shifts
in volatility, trend, or market microstructure?
"""

import warnings
from datetime import datetime
from math import erf

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

print("=" * 80)
print("REGIME DETECTION - Deviation Clustering Analysis")
print("=" * 80)

# Configuration
STANDARD_FILE = "/tmp/Exness_EURUSD_2024_09.csv"
RAW_SPREAD_FILE = "/tmp/Exness_EURUSD_Raw_Spread_2024_09.csv"
ZERO_SPREAD_THRESHOLD = 0.00001
DEVIATION_THRESHOLDS = {"bid_biased": 0.4, "ask_biased": 0.6}
CLUSTER_WINDOW = 60  # seconds - deviations within 60s are considered a cluster
MIN_CLUSTER_SIZE = 3  # minimum deviations to be considered a cluster
REGIME_LOOKBACK = 300  # seconds - measure regime before cluster
REGIME_LOOKAHEAD = 300  # seconds - measure regime after cluster

print("\n📊 Configuration:")
print(f"   Cluster window: {CLUSTER_WINDOW}s (deviations within this window = cluster)")
print(f"   Min cluster size: {MIN_CLUSTER_SIZE} deviations")
print(f"   Regime measurement: {REGIME_LOOKBACK}s before/after")

# Load data
print("\n1️⃣  Loading data...")
std_df = pd.read_csv(STANDARD_FILE, parse_dates=["Timestamp"], usecols=["Timestamp", "Bid", "Ask"])
raw_df = pd.read_csv(
    RAW_SPREAD_FILE, parse_dates=["Timestamp"], usecols=["Timestamp", "Bid", "Ask"]
)

std_df["mid"] = (std_df["Bid"] + std_df["Ask"]) / 2
std_df["spread"] = std_df["Ask"] - std_df["Bid"]
raw_df["mid"] = (raw_df["Bid"] + raw_df["Ask"]) / 2
raw_df["spread"] = raw_df["Ask"] - raw_df["Bid"]

zero_spread_df = raw_df[raw_df["spread"] <= ZERO_SPREAD_THRESHOLD].copy()

std_df = std_df.sort_values("Timestamp").reset_index(drop=True)
zero_spread_df = zero_spread_df.sort_values("Timestamp").reset_index(drop=True)

# Merge datasets
merged_df = pd.merge_asof(
    zero_spread_df[["Timestamp", "mid"]].rename(columns={"mid": "raw_mid"}),
    std_df[["Timestamp", "Bid", "Ask", "mid", "spread"]].rename(
        columns={"Bid": "std_bid", "Ask": "std_ask", "mid": "std_mid", "spread": "std_spread"}
    ),
    on="Timestamp",
    direction="backward",
    tolerance=pd.Timedelta(seconds=10),
)
merged_df = merged_df.dropna()

merged_df["position_ratio"] = (merged_df["raw_mid"] - merged_df["std_bid"]) / (
    merged_df["std_ask"] - merged_df["std_bid"]
)

print(f"   ✅ Matched ticks: {len(merged_df):,}")

# Filter to deviations only
merged_df["deviation_type"] = "normal"
merged_df.loc[
    merged_df["position_ratio"] < DEVIATION_THRESHOLDS["bid_biased"], "deviation_type"
] = "bid_biased"
merged_df.loc[
    merged_df["position_ratio"] > DEVIATION_THRESHOLDS["ask_biased"], "deviation_type"
] = "ask_biased"

deviation_df = merged_df[merged_df["deviation_type"] != "normal"].copy()
deviation_df = deviation_df.sort_values("Timestamp").reset_index(drop=True)

print(f"   Deviations: {len(deviation_df):,} ({len(deviation_df) / len(merged_df) * 100:.1f}%)")

# Identify deviation clusters
print("\n2️⃣  Identifying deviation clusters...")

deviation_df["time_to_next"] = deviation_df["Timestamp"].diff(-1).abs().dt.total_seconds()
deviation_df["is_clustered"] = deviation_df["time_to_next"].shift(1) <= CLUSTER_WINDOW

# Group into clusters
clusters = []
current_cluster = []

for idx, row in deviation_df.iterrows():
    if row["is_clustered"] and len(current_cluster) > 0:
        current_cluster.append(
            {
                "timestamp": row["Timestamp"],
                "position_ratio": row["position_ratio"],
                "deviation_type": row["deviation_type"],
            }
        )
    else:
        # Save previous cluster if meets size requirement
        if len(current_cluster) >= MIN_CLUSTER_SIZE:
            cluster_start = current_cluster[0]["timestamp"]
            cluster_end = current_cluster[-1]["timestamp"]
            cluster_duration = (cluster_end - cluster_start).total_seconds()

            clusters.append(
                {
                    "start_time": cluster_start,
                    "end_time": cluster_end,
                    "duration_sec": cluster_duration,
                    "size": len(current_cluster),
                    "mean_position": np.mean([d["position_ratio"] for d in current_cluster]),
                    "dominant_type": max(
                        {d["deviation_type"] for d in current_cluster},
                        key=[d["deviation_type"] for d in current_cluster].count,
                    ),
                }
            )

        # Start new cluster
        current_cluster = [
            {
                "timestamp": row["Timestamp"],
                "position_ratio": row["position_ratio"],
                "deviation_type": row["deviation_type"],
            }
        ]

# Save last cluster
if len(current_cluster) >= MIN_CLUSTER_SIZE:
    cluster_start = current_cluster[0]["timestamp"]
    cluster_end = current_cluster[-1]["timestamp"]
    cluster_duration = (cluster_end - cluster_start).total_seconds()

    clusters.append(
        {
            "start_time": cluster_start,
            "end_time": cluster_end,
            "duration_sec": cluster_duration,
            "size": len(current_cluster),
            "mean_position": np.mean([d["position_ratio"] for d in current_cluster]),
            "dominant_type": max(
                {d["deviation_type"] for d in current_cluster},
                key=[d["deviation_type"] for d in current_cluster].count,
            ),
        }
    )

clusters_df = pd.DataFrame(clusters)
print(f"   ✅ Identified {len(clusters_df):,} clusters (size ≥{MIN_CLUSTER_SIZE})")

if len(clusters_df) > 0:
    print("   Cluster statistics:")
    print(f"   ├─ Mean size: {clusters_df['size'].mean():.1f} deviations")
    print(f"   ├─ Mean duration: {clusters_df['duration_sec'].mean():.1f}s")
    print(f"   ├─ Bid-biased clusters: {(clusters_df['dominant_type'] == 'bid_biased').sum():,}")
    print(f"   └─ Ask-biased clusters: {(clusters_df['dominant_type'] == 'ask_biased').sum():,}")

# Regime measurement
print("\n3️⃣  Measuring regimes around clusters...")

std_df_indexed = std_df.set_index("Timestamp").sort_index()


def measure_regime(start_ts, end_ts, std_indexed):
    """Measure volatility, trend, and spread regime in a time window"""
    data = std_indexed[(std_indexed.index >= start_ts) & (std_indexed.index < end_ts)]

    if len(data) < 2:
        return {"volatility": np.nan, "trend": np.nan, "mean_spread": np.nan, "tick_count": 0}

    returns = data["mid"].pct_change().dropna()
    volatility = returns.std() * 10000 if len(returns) > 0 else np.nan
    trend = (data["mid"].iloc[-1] - data["mid"].iloc[0]) / data["mid"].iloc[0] * 10000
    mean_spread = data["spread"].mean() * 10000

    return {
        "volatility": volatility,
        "trend": trend,
        "mean_spread": mean_spread,
        "tick_count": len(data),
    }


# Sample clusters for performance
sample_size = min(500, len(clusters_df))
print(f"   Sampling {sample_size:,} clusters for regime analysis...")
clusters_sample = clusters_df.sample(n=sample_size, random_state=42).copy()

# Measure before/after regimes
before_regimes = []
after_regimes = []

for idx, cluster in clusters_sample.iterrows():
    # Before regime
    before_start = cluster["start_time"] - pd.Timedelta(seconds=REGIME_LOOKBACK)
    before_end = cluster["start_time"]
    before_regime = measure_regime(before_start, before_end, std_df_indexed)

    # After regime
    after_start = cluster["end_time"]
    after_end = cluster["end_time"] + pd.Timedelta(seconds=REGIME_LOOKAHEAD)
    after_regime = measure_regime(after_start, after_end, std_df_indexed)

    before_regimes.append(before_regime)
    after_regimes.append(after_regime)

# Add regime measurements to clusters
for key in ["volatility", "trend", "mean_spread", "tick_count"]:
    clusters_sample[f"before_{key}"] = [r[key] for r in before_regimes]
    clusters_sample[f"after_{key}"] = [r[key] for r in after_regimes]

# Calculate regime shifts
clusters_sample = clusters_sample.dropna(subset=["before_volatility", "after_volatility"])
clusters_sample["volatility_shift"] = (
    clusters_sample["after_volatility"] - clusters_sample["before_volatility"]
)
clusters_sample["volatility_shift_pct"] = (
    clusters_sample["volatility_shift"] / clusters_sample["before_volatility"] * 100
)
clusters_sample["trend_shift"] = clusters_sample["after_trend"] - clusters_sample["before_trend"]
clusters_sample["spread_shift"] = (
    clusters_sample["after_mean_spread"] - clusters_sample["before_mean_spread"]
)

# Classify regime shifts
clusters_sample["regime_change"] = "none"
clusters_sample.loc[clusters_sample["volatility_shift_pct"] > 20, "regime_change"] = "vol_increase"
clusters_sample.loc[clusters_sample["volatility_shift_pct"] < -20, "regime_change"] = "vol_decrease"

print(f"   ✅ Measured regimes for {len(clusters_sample):,} clusters")

# Analysis
print("\n4️⃣  Regime Shift Analysis")
print("=" * 80)

# Overall regime change statistics
volatility_increased = (clusters_sample["volatility_shift"] > 0).sum()
volatility_decreased = (clusters_sample["volatility_shift"] < 0).sum()
significant_vol_increase = (clusters_sample["volatility_shift_pct"] > 20).sum()
significant_vol_decrease = (clusters_sample["volatility_shift_pct"] < -20).sum()

print("\n📊 Volatility Regime Shifts:")
print("-" * 80)
print(
    f"   Increased volatility: {volatility_increased:,} ({volatility_increased / len(clusters_sample) * 100:.1f}%)"
)
print(
    f"   Decreased volatility: {volatility_decreased:,} ({volatility_decreased / len(clusters_sample) * 100:.1f}%)"
)
print(
    f"   Significant increase (>20%): {significant_vol_increase:,} ({significant_vol_increase / len(clusters_sample) * 100:.1f}%)"
)
print(
    f"   Significant decrease (<-20%): {significant_vol_decrease:,} ({significant_vol_decrease / len(clusters_sample) * 100:.1f}%)"
)

print("\n   Mean changes:")
print(
    f"   ├─ Volatility: {clusters_sample['volatility_shift'].mean():+.4f} bps ({clusters_sample['volatility_shift_pct'].mean():+.1f}%)"
)
print(f"   ├─ Trend: {clusters_sample['trend_shift'].mean():+.4f} bps")
print(f"   └─ Spread: {clusters_sample['spread_shift'].mean():+.4f} bps")

# By cluster type
print("\n📊 By Cluster Type:")
print("-" * 80)

for cluster_type in ["bid_biased", "ask_biased"]:
    type_clusters = clusters_sample[clusters_sample["dominant_type"] == cluster_type]

    if len(type_clusters) == 0:
        continue

    vol_increase = (type_clusters["volatility_shift"] > 0).sum()
    vol_sig_increase = (type_clusters["volatility_shift_pct"] > 20).sum()

    print(f"\n   {cluster_type.upper()} (N={len(type_clusters):,}):")
    print(f"   ├─ Vol increases: {vol_increase:,} ({vol_increase / len(type_clusters) * 100:.1f}%)")
    print(
        f"   ├─ Sig vol increases: {vol_sig_increase:,} ({vol_sig_increase / len(type_clusters) * 100:.1f}%)"
    )
    print(
        f"   ├─ Mean vol shift: {type_clusters['volatility_shift'].mean():+.4f} bps ({type_clusters['volatility_shift_pct'].mean():+.1f}%)"
    )
    print(f"   └─ Mean trend shift: {type_clusters['trend_shift'].mean():+.4f} bps")

# By cluster size
print("\n📊 By Cluster Size:")
print("-" * 80)

size_quartiles = clusters_sample["size"].quantile([0.25, 0.5, 0.75]).values
size_bins = [
    clusters_sample["size"].min(),
    size_quartiles[0],
    size_quartiles[1],
    size_quartiles[2],
    clusters_sample["size"].max(),
]
size_labels = ["Small", "Medium", "Large", "XLarge"]

clusters_sample["size_category"] = pd.cut(
    clusters_sample["size"], bins=size_bins, labels=size_labels, include_lowest=True
)

for size_cat in size_labels:
    size_clusters = clusters_sample[clusters_sample["size_category"] == size_cat]

    if len(size_clusters) == 0:
        continue

    vol_sig_increase = (size_clusters["volatility_shift_pct"] > 20).sum()

    print(
        f"\n   {size_cat} clusters (N={len(size_clusters):,}, size={size_clusters['size'].min():.0f}-{size_clusters['size'].max():.0f}):"
    )
    print(
        f"   ├─ Sig vol increases: {vol_sig_increase:,} ({vol_sig_increase / len(size_clusters) * 100:.1f}%)"
    )
    print(f"   └─ Mean vol shift: {size_clusters['volatility_shift_pct'].mean():+.1f}%")

# Statistical test: Do clusters predict regime shifts?
print("\n📊 Predictive Power Assessment:")
print("-" * 80)

baseline_vol_increase_rate = 0.50  # Null hypothesis: 50% random chance
observed_vol_increase_rate = volatility_increased / len(clusters_sample)

# Simple binomial test (manual implementation)
n = len(clusters_sample)
k = volatility_increased

# Calculate z-score for proportion test
p0 = baseline_vol_increase_rate
p_obs = observed_vol_increase_rate
se = np.sqrt(p0 * (1 - p0) / n)
z_score = (p_obs - p0) / se

# Two-tailed p-value from z-score (approximate)
p_value = 2 * (1 - 0.5 * (1 + erf(abs(z_score) / np.sqrt(2))))

print("\n   Null Hypothesis: Clusters have no predictive power (50% vol increase expected)")
print(f"   Observed: {observed_vol_increase_rate * 100:.1f}% volatility increases")
print(f"   Z-score: {z_score:.3f}")
print(f"   P-value: {p_value:.4f} {'✅ SIGNIFICANT' if p_value < 0.05 else '❌ NOT SIGNIFICANT'}")

# Effect size
effect_size = observed_vol_increase_rate - baseline_vol_increase_rate
print(f"   Effect size: {effect_size * 100:+.1f} percentage points")

# Save results
results_summary = {
    "total_clusters": len(clusters_sample),
    "vol_increase_pct": volatility_increased / len(clusters_sample) * 100,
    "vol_decrease_pct": volatility_decreased / len(clusters_sample) * 100,
    "sig_vol_increase_pct": significant_vol_increase / len(clusters_sample) * 100,
    "sig_vol_decrease_pct": significant_vol_decrease / len(clusters_sample) * 100,
    "mean_vol_shift_bps": clusters_sample["volatility_shift"].mean(),
    "mean_vol_shift_pct": clusters_sample["volatility_shift_pct"].mean(),
    "mean_trend_shift_bps": clusters_sample["trend_shift"].mean(),
    "mean_spread_shift_bps": clusters_sample["spread_shift"].mean(),
    "predictive_power_p_value": p_value,
    "effect_size_pct": effect_size * 100,
}

pd.DataFrame([results_summary]).to_csv("/tmp/regime_detection_results.csv", index=False)
clusters_sample.to_csv("/tmp/regime_detection_clusters.csv", index=False)

print("\n✅ Saved: /tmp/regime_detection_results.csv")
print("✅ Saved: /tmp/regime_detection_clusters.csv")

# Generate report
print("\n5️⃣  Generating report...")

report = f"""# Regime Detection via Deviation Clustering
## Research Report

**Generated:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## Executive Summary

This analysis tests whether clusters of zero-spread deviations predict regime shifts in
volatility, trend, or market microstructure.

### Key Findings

**Regime Shift Prediction: {"✅ SIGNIFICANT" if p_value < 0.05 else "❌ NOT SIGNIFICANT"}**

"""

if observed_vol_increase_rate > baseline_vol_increase_rate:
    report += f"""
Deviation clusters predict **volatility increases** at a rate of {observed_vol_increase_rate * 100:.1f}%,
compared to {baseline_vol_increase_rate * 100:.0f}% baseline expectation (p={p_value:.4f}).

**Effect size:** {effect_size * 100:+.1f} percentage points
"""
else:
    report += f"""
Deviation clusters do **NOT** predict volatility increases ({observed_vol_increase_rate * 100:.1f}%
vs {baseline_vol_increase_rate * 100:.0f}% expected, p={p_value:.4f}).

No significant regime detection power identified.
"""

report += f"""

### Cluster Statistics

- **Total clusters identified:** {len(clusters_df):,}
- **Analyzed sample:** {len(clusters_sample):,}
- **Mean cluster size:** {clusters_sample["size"].mean():.1f} deviations
- **Mean cluster duration:** {clusters_sample["duration_sec"].mean():.1f} seconds

### Regime Changes Observed

1. **Volatility Shifts**
   - Increased: {volatility_increased:,} ({volatility_increased / len(clusters_sample) * 100:.1f}%)
   - Decreased: {volatility_decreased:,} ({volatility_decreased / len(clusters_sample) * 100:.1f}%)
   - Significant increase (>20%): {significant_vol_increase:,} ({significant_vol_increase / len(clusters_sample) * 100:.1f}%)

2. **Trend Shifts**
   - Mean change: {clusters_sample["trend_shift"].mean():+.4f} bps

3. **Spread Shifts**
   - Mean change: {clusters_sample["spread_shift"].mean():+.4f} bps

## Methodology

### Cluster Identification

**Definition:** A cluster is a group of {MIN_CLUSTER_SIZE}+ deviations occurring within {CLUSTER_WINDOW}s windows.

**Process:**
1. Identify all zero-spread deviations (bid <0.4 or ask >0.6)
2. Group consecutive deviations within {CLUSTER_WINDOW}s
3. Retain clusters with ≥{MIN_CLUSTER_SIZE} deviations

### Regime Measurement

**Before Regime:** {REGIME_LOOKBACK}s before cluster start
**After Regime:** {REGIME_LOOKAHEAD}s after cluster end

**Metrics:**
- Volatility: Standard deviation of returns (bps)
- Trend: Price change over period (bps)
- Spread: Mean bid-ask spread (bps)

### Statistical Test

**Null Hypothesis:** Clusters have no predictive power (50% chance of vol increase)
**Alternative:** Clusters predict volatility regime shifts
**Test:** Binomial test (two-sided)
**Significance:** α = 0.05

## Results by Cluster Type

"""

for cluster_type in ["bid_biased", "ask_biased"]:
    type_clusters = clusters_sample[clusters_sample["dominant_type"] == cluster_type]

    if len(type_clusters) == 0:
        continue

    vol_increase = (type_clusters["volatility_shift"] > 0).sum()
    vol_sig_increase = (type_clusters["volatility_shift_pct"] > 20).sum()

    report += f"""
### {cluster_type.replace("_", " ").title()} Clusters

- **Count:** {len(type_clusters):,}
- **Vol increases:** {vol_increase:,} ({vol_increase / len(type_clusters) * 100:.1f}%)
- **Sig vol increases:** {vol_sig_increase:,} ({vol_sig_increase / len(type_clusters) * 100:.1f}%)
- **Mean vol shift:** {type_clusters["volatility_shift"].mean():+.4f} bps ({type_clusters["volatility_shift_pct"].mean():+.1f}%)
- **Mean trend shift:** {type_clusters["trend_shift"].mean():+.4f} bps
"""

report += """

## Interpretation

### Microstructure Perspective

"""

if observed_vol_increase_rate > baseline_vol_increase_rate and p_value < 0.05:
    report += f"""
**Clusters are regime markers.** When deviations cluster together, it signals:

1. **Liquidity stress** - Market makers struggling to maintain quotes
2. **Information arrival** - News/data causing price discovery issues
3. **Volatility breakout** - Calm → volatile transition underway

The {effect_size * 100:+.1f}pp increase in volatility probability is statistically significant
and economically meaningful for risk management.
"""
else:
    report += f"""
**Clusters are NOT regime markers.** Deviation clustering does not predict regime shifts.

Possible explanations:
1. Clusters are random noise, not information signals
2. {CLUSTER_WINDOW}s window too short to capture meaningful patterns
3. Sep 2024 specific - pattern may not generalize
"""

report += """

### Trading Implications

"""

if observed_vol_increase_rate > baseline_vol_increase_rate and p_value < 0.05:
    report += f"""
**Risk Management Strategy:**

1. **Detect cluster formation**
   - Monitor deviation frequency in rolling {CLUSTER_WINDOW}s windows
   - Alert when ≥{MIN_CLUSTER_SIZE} deviations occur

2. **Adjust position sizing**
   - Reduce exposure when cluster detected
   - Expect volatility increase of {clusters_sample["volatility_shift_pct"].mean():.1f}% on average

3. **Widen stops**
   - Increase stop distance by ~{clusters_sample["volatility_shift_pct"].mean():.0f}%
   - Prevent premature stop-outs during regime shift

4. **Timing**
   - Volatility shift occurs within {REGIME_LOOKAHEAD}s
   - Adjust immediately upon cluster detection
"""
else:
    report += """
**No actionable strategy identified.**

Deviation clusters do not provide reliable regime shift signals. Continue using
established volatility forecasting methods (GARCH, implied volatility, etc.).
"""

report += f"""

## Limitations

1. **Definition Sensitivity**
   - Cluster definition ({CLUSTER_WINDOW}s window, {MIN_CLUSTER_SIZE}+ size) is arbitrary
   - Different parameters may yield different results

2. **Sample Size**
   - Analyzed {len(clusters_sample):,} out of {len(clusters_df):,} clusters
   - May miss rare but important patterns

3. **Single Period**
   - Sep 2024 only - needs multi-period validation
   - EUR/USD specific - may not generalize to other pairs

4. **Regime Measurement**
   - {REGIME_LOOKBACK}s lookback/ahead may be too short/long
   - Alternative regime definitions (GARCH, structural breaks) not tested

## Recommended Next Steps

### Priority 1: Parameter Sensitivity
- Test different cluster windows (30s, 120s, 300s)
- Test different size thresholds (5, 10, 20 deviations)
- Identify optimal cluster definition

### Priority 2: Alternative Regime Metrics
- Test GARCH volatility models
- Test realized volatility (high-frequency)
- Test order flow imbalance

### Priority 3: Multi-Period Validation
- Test on Jan-Aug 2024
- Check if pattern stable across time
- Identify regime-specific behavior

### Priority 4: Cross-Pair Validation
- Test GBP/USD, USD/JPY
- Compare cluster-regime relationships
- Build universal vs pair-specific models

## Conclusion

"""

if observed_vol_increase_rate > baseline_vol_increase_rate and p_value < 0.05:
    conclusion = f"""
**Deviation clusters ARE regime shift predictors.**

Clusters predict volatility increases at {observed_vol_increase_rate * 100:.1f}% rate
(p={p_value:.4f}), significantly above {baseline_vol_increase_rate * 100:.0f}% baseline.

Effect size of {effect_size * 100:+.1f}pp provides actionable edge for risk management.

**Key insight:** When deviations cluster, expect volatility breakout within {REGIME_LOOKAHEAD}s.
Reduce exposure, widen stops, and prepare for regime shift.
"""
else:
    conclusion = f"""
**Deviation clusters do NOT predict regime shifts.**

Observed volatility increase rate ({observed_vol_increase_rate * 100:.1f}%) is not significantly
different from baseline ({baseline_vol_increase_rate * 100:.0f}%, p={p_value:.4f}).

**Key insight:** Clustering is noise, not signal. Use established volatility forecasting
methods instead of deviation cluster monitoring.
"""

report += conclusion

with open("/tmp/regime_detection_report.md", "w") as f:
    f.write(report)

print("✅ Saved: /tmp/regime_detection_report.md")

print("\n" + "=" * 80)
print("✅ REGIME DETECTION ANALYSIS COMPLETE")
print("=" * 80)

print("\n📊 Key Findings:")
print(f"   Clusters identified: {len(clusters_df):,}")
print(
    f"   Predictive power: p={p_value:.4f} {'✅ SIGNIFICANT' if p_value < 0.05 else '❌ NOT SIGNIFICANT'}"
)
print(
    f"   Vol increase rate: {observed_vol_increase_rate * 100:.1f}% (baseline {baseline_vol_increase_rate * 100:.0f}%)"
)
print(f"   Effect size: {effect_size * 100:+.1f} percentage points")
print(f"   Mean vol shift: {clusters_sample['volatility_shift_pct'].mean():+.1f}%")
