#!/usr/bin/env python3
"""
Phase 6 Visualization - Lightweight Interactive Dashboard
Version: 1.0.0
Date: 2025-10-06

Creates performant interactive HTML dashboard by aggressively downsampling:
- 1-minute bars only (not 5s/15s)
- Sample 5000 deviations max per risk level
- Simplified burst highlighting (count only, no shapes)

Target: <30 second generation time, <3MB HTML file
"""

import sys
from pathlib import Path
import pandas as pd
import json
import logging
import plotly.graph_objects as go

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Paths
DATA_DIR = Path("/tmp")
OUTPUT_DIR = Path("/tmp")

# Color scheme - 6-level risk gradient
COLORS = {
    5: '#8B00FF',  # Purple - Extreme risk
    4: '#FF0000',  # Red - High risk
    3: '#FF8800',  # Orange - Elevated risk
    2: '#FFD700',  # Yellow - Moderate risk
    1: '#00CC00',  # Green - Low risk
    0: '#0066FF',  # Blue - Minimal risk
    'candle': '#D0D0D0'  # Very light gray candlesticks (blends with white background)
}

def load_visualization_data(year: str, month: str) -> dict:
    """Load prepared visualization data (1m bars only)"""
    month_str = f"{year}-{month}"
    logger.info(f"Loading visualization data: {month_str}")

    with open(DATA_DIR / f"viz_{month_str}_metadata.json") as f:
        metadata = json.load(f)

    viz_data = {
        'metadata': metadata,
        'ohlc_1m': pd.read_parquet(DATA_DIR / f"viz_{month_str}_ohlc_1m.parquet"),
        'deviations': pd.read_parquet(DATA_DIR / f"viz_{month_str}_deviations.parquet"),
        'trading_zones': pd.read_parquet(DATA_DIR / f"viz_{month_str}_trading_zones.parquet")
    }

    logger.info(f"  Loaded: {len(viz_data['ohlc_1m'])} 1m bars")
    logger.info(f"  Loaded: {len(viz_data['deviations'])} deviations")

    return viz_data

def add_burst_decay_lines(fig: go.Figure, deviations: pd.DataFrame):
    """
    Add horizontal lines showing burst persistence effect (fading over time).

    Lines extend rightward from burst events with decreasing opacity to show
    diminishing effect over time.

    Using add_shape() with datetime coordinates (canonical Plotly method).
    """
    burst_events = deviations[deviations['is_burst']].copy()

    if len(burst_events) == 0:
        logger.info("  No burst events to visualize")
        return

    # Sample bursts conservatively to avoid visual clutter
    if len(burst_events) > 30:
        burst_events = burst_events.sample(n=30, random_state=42)
        logger.info(f"  Sampled 30 of {len(deviations[deviations['is_burst']])} burst events")

    logger.info(f"  Adding {len(burst_events)} burst decay lines...")

    decay_duration = pd.Timedelta('1h')  # 1 hour for better visibility at zoom levels
    n_segments = 5  # Fewer segments for cleaner appearance

    for _, burst in burst_events.iterrows():
        color = COLORS[burst['risk_level']]
        start_time = burst['Timestamp']
        price = burst['price']

        # Create fading segments with reduced opacity to prevent stacking
        for i in range(n_segments):
            segment_start = start_time + (i * decay_duration / n_segments)
            segment_end = start_time + ((i + 1) * decay_duration / n_segments)
            opacity = 0.4 * (1 - i / n_segments)  # Start at 0.4 (was 0.9) to reduce stacking

            fig.add_shape(
                type="line",
                x0=segment_start,
                y0=price,
                x1=segment_end,
                y1=price,
                line_color=color,
                line_width=3,  # Reduced from 6 to 3 for thinner lines
                opacity=opacity,
                layer="above"
            )

def generate_lightweight_dashboard(year: str, month: str) -> Path:
    """Generate performant dashboard"""
    month_str = f"{year}-{month}"
    logger.info(f"\n{'='*80}")
    logger.info(f"Generating Lightweight Dashboard: {month_str}")
    logger.info(f"{'='*80}")

    viz_data = load_visualization_data(year, month)

    # Sample deviations by risk level (0-5)
    logger.info("\nSampling deviations for performance...")
    deviations = viz_data['deviations']

    sampled_parts = []
    for risk_level in [5, 4, 3, 2, 1, 0]:
        subset = deviations[deviations['risk_level'] == risk_level]

        if risk_level >= 4:  # Keep all Purple/Red (extreme risk)
            sampled_parts.append(subset)
        elif risk_level == 3 and len(subset) > 5000:  # Sample Orange
            sampled_parts.append(subset.sample(n=5000, random_state=42))
        elif risk_level == 2 and len(subset) > 3000:  # Sample Yellow
            sampled_parts.append(subset.sample(n=3000, random_state=42))
        elif risk_level <= 1 and len(subset) > 1000:  # Minimal Green/Blue
            sampled_parts.append(subset.sample(n=1000, random_state=42))
        else:
            sampled_parts.append(subset)

    sampled_deviations = pd.concat(sampled_parts) if sampled_parts else pd.DataFrame()
    logger.info(f"  Sampled: {len(sampled_deviations)} / {len(deviations)} events")

    # Log distribution
    for risk_level in [5, 4, 3, 2, 1, 0]:
        count = len(sampled_deviations[sampled_deviations['risk_level'] == risk_level])
        logger.info(f"    Level {risk_level}: {count}")

    # Create figure
    logger.info("\nCreating figure...")
    fig = go.Figure()

    # Add candlesticks (grayscale for better deviation marker visibility)
    logger.info("  Adding 1-minute candlesticks...")
    ohlc = viz_data['ohlc_1m']
    fig.add_trace(go.Candlestick(
        x=ohlc['Timestamp'],
        open=ohlc['open'],
        high=ohlc['high'],
        low=ohlc['low'],
        close=ohlc['close'],
        name='1min',
        increasing_line_color=COLORS['candle'],
        decreasing_line_color=COLORS['candle'],
        increasing_fillcolor=COLORS['candle'],
        decreasing_fillcolor=COLORS['candle']
    ))

    # Add burst decay lines (before other elements for layering)
    logger.info("  Adding burst decay lines...")
    add_burst_decay_lines(fig, sampled_deviations)

    # Add deviation markers (by risk level 0-5)
    logger.info("  Adding deviation markers...")
    for risk_level in [5, 4, 3, 2, 1, 0]:
        subset = sampled_deviations[sampled_deviations['risk_level'] == risk_level]
        if len(subset) == 0:
            continue

        fig.add_trace(go.Scatter(
            x=subset['Timestamp'],
            y=subset['price'],
            mode='markers',
            marker=dict(
                color=COLORS[risk_level],
                size=8,  # Increased from 6 to 8 for better visibility
                opacity=0.85,  # Increased from 0.7 for stronger presence
                symbol='circle',
                line=dict(width=0)
            ),
            name=f'Level {risk_level} ({len(subset)})',
            text=[
                f"Time: {ts}<br>Price: {p:.5f}<br>Deviation: {d:.3f}<br>Risk Level: {risk_level}<br>"
                f"Enrichment: {e:.2f}x<br>CV: {cv:.1f}<br>Burst%: {b:.1f}%"
                for ts, p, d, e, cv, b in zip(
                    subset['Timestamp'], subset['price'], subset['deviation'],
                    subset['rolling_enrichment'], subset['rolling_cv'], subset['rolling_burst_pct']
                )
            ],
            hoverinfo='text'
        ))

    # Configure layout
    metadata = viz_data['metadata']
    fig.update_layout(
        title=dict(
            text=f"EUR/USD Zero-Spread Deviations - {month_str} (Dynamic Rolling Risk)<br>" +
                 f"<sub>{metadata['n_deviations']:,} total events | " +
                 f"Risk Levels: 5=Purple (Extreme), 4=Red (High), 3=Orange (Elevated), 2=Yellow (Moderate), 1=Green (Low), 0=Blue (Minimal)</sub>",
            x=0.5,
            xanchor='center'
        ),
        height=800,
        hovermode='x unified',
        xaxis_rangeslider_visible=False,
        showlegend=True,
        template='plotly_white',
        yaxis_title="Price (EUR/USD)",
        xaxis_title="Time (UTC)"
    )

    # Save to HTML
    output_path = OUTPUT_DIR / f"eurusd_deviation_dashboard_{month_str}_lightweight.html"
    logger.info(f"\nSaving dashboard to: {output_path}")

    fig.write_html(
        str(output_path),
        config={
            'displayModeBar': True,
            'displaylogo': False,
            'modeBarButtonsToRemove': ['lasso2d', 'select2d']
        }
    )

    file_size_mb = output_path.stat().st_size / 1024 / 1024
    logger.info(f"  ✓ Saved: {output_path} ({file_size_mb:.1f} MB)")

    logger.info(f"\n{'='*80}")
    logger.info(f"✅ Dashboard complete: {month_str}")
    logger.info(f"{'='*80}")
    logger.info(f"\nOpen in browser: file://{output_path}")

    return output_path

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Generate lightweight interactive dashboard')
    parser.add_argument('--year', type=str, required=True, help='Year (e.g., 2024)')
    parser.add_argument('--month', type=str, required=True, help='Month (01-12)')

    args = parser.parse_args()

    try:
        output_path = generate_lightweight_dashboard(args.year, args.month)
        logger.info(f"\n✅ Success! Dashboard saved to: {output_path}")
    except Exception as e:
        logger.error(f"\n❌ Dashboard generation failed: {e}")
        raise

if __name__ == "__main__":
    main()
