#!/usr/bin/env python3
"""
Phase 6 Visualization - Interactive Dashboard Generator
Version: 1.0.0
Date: 2025-10-06

Creates interactive HTML dashboard with Plotly showing zero-spread deviation patterns
overlaid on EUR/USD price action at multiple timeframes (5s, 15s, 1m bars).

Features:
- Multi-timeframe synchronized candlestick charts
- Deviation event markers (color-coded by risk level)
- Hot zone bands (RED/YELLOW shading)
- Burst period highlighting
- Interactive zoom, pan, hover tooltips

SLOs:
- Availability: 100% (dashboard generated or fail explicitly)
- Correctness: Exact timestamp alignment, color-code matching risk levels
- Observability: Chart generation progress logged
- Maintainability: Plotly graph_objects only, no custom rendering

Dependencies:
- Visualization data from prepare_visualization_data.py
- plotly>=5.0.0
"""

import sys
from pathlib import Path
import pandas as pd
import json
import logging
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Paths
DATA_DIR = Path("/tmp")
OUTPUT_DIR = Path("/tmp")

# Color scheme
COLORS = {
    'RED': '#FF4444',
    'YELLOW': '#FFAA00',
    'NONE': '#888888',
    'up_candle': '#26A69A',
    'down_candle': '#EF5350',
    'burst_bg': 'rgba(255, 100, 100, 0.1)'
}

class DashboardGenerationError(Exception):
    """Raised when dashboard generation fails"""
    pass

def load_visualization_data(year: str, month: str) -> dict:
    """
    Load prepared visualization data.

    Returns:
        Dictionary with all dataframes and metadata
    """
    month_str = f"{year}-{month}"
    logger.info(f"Loading visualization data: {month_str}")

    # Load metadata
    metadata_path = DATA_DIR / f"viz_{month_str}_metadata.json"
    if not metadata_path.exists():
        raise FileNotFoundError(f"Missing metadata: {metadata_path}")

    with open(metadata_path) as f:
        metadata = json.load(f)

    # Load parquet files
    viz_data = {
        'metadata': metadata,
        'ohlc_5s': pd.read_parquet(DATA_DIR / f"viz_{month_str}_ohlc_5s.parquet"),
        'ohlc_15s': pd.read_parquet(DATA_DIR / f"viz_{month_str}_ohlc_15s.parquet"),
        'ohlc_1m': pd.read_parquet(DATA_DIR / f"viz_{month_str}_ohlc_1m.parquet"),
        'deviations': pd.read_parquet(DATA_DIR / f"viz_{month_str}_deviations.parquet"),
        'hot_zones': pd.read_parquet(DATA_DIR / f"viz_{month_str}_hot_zones.parquet"),
        'trading_zones': pd.read_parquet(DATA_DIR / f"viz_{month_str}_trading_zones.parquet")
    }

    logger.info(f"  Loaded: {len(viz_data['ohlc_5s'])} 5s bars")
    logger.info(f"  Loaded: {len(viz_data['ohlc_15s'])} 15s bars")
    logger.info(f"  Loaded: {len(viz_data['ohlc_1m'])} 1m bars")
    logger.info(f"  Loaded: {len(viz_data['deviations'])} deviations")

    return viz_data

def create_candlestick_trace(df: pd.DataFrame, name: str) -> go.Candlestick:
    """Create candlestick trace"""
    return go.Candlestick(
        x=df['Timestamp'],
        open=df['open'],
        high=df['high'],
        low=df['low'],
        close=df['close'],
        name=name,
        increasing_line_color=COLORS['up_candle'],
        decreasing_line_color=COLORS['down_candle'],
        showlegend=False
    )

def add_deviation_markers(fig: go.Figure, deviations: pd.DataFrame, row: int, sample_size: int = 10000):
    """Add deviation event scatter markers (sampled for performance)"""

    # Sample for performance (keep all RED, sample others)
    red_subset = deviations[deviations['risk_level'] == 'RED']
    yellow_subset = deviations[deviations['risk_level'] == 'YELLOW']
    none_subset = deviations[deviations['risk_level'] == 'NONE']

    # Sample YELLOW and NONE if too many
    if len(yellow_subset) > sample_size:
        yellow_subset = yellow_subset.sample(n=sample_size, random_state=42)
    if len(none_subset) > sample_size:
        none_subset = none_subset.sample(n=sample_size, random_state=42)

    # Split by risk level for different colors
    for risk_level, color, dev_subset in [
        ('RED', COLORS['RED'], red_subset),
        ('YELLOW', COLORS['YELLOW'], yellow_subset),
        ('NONE', COLORS['NONE'], none_subset)
    ]:
        if len(dev_subset) == 0:
            continue

        fig.add_trace(
            go.Scatter(
                x=dev_subset['Timestamp'],
                y=dev_subset['price'],
                mode='markers',
                marker=dict(
                    color=color,
                    size=dev_subset['deviation'] * 20,  # Scale by magnitude
                    opacity=0.6,
                    line=dict(width=0.5, color='white')
                ),
                name=f'{risk_level} Zone',
                text=[
                    f"Time: {ts}<br>"
                    f"Price: {p:.5f}<br>"
                    f"Deviation: {d:.3f}<br>"
                    f"Position: {pr:.3f}<br>"
                    f"Risk: {risk_level}"
                    for ts, p, d, pr in zip(
                        dev_subset['Timestamp'],
                        dev_subset['price'],
                        dev_subset['deviation'],
                        dev_subset['position_ratio']
                    )
                ],
                hoverinfo='text',
                showlegend=(row == 1)  # Only show legend once
            ),
            row=row,
            col=1
        )

def add_hot_zone_bands(fig: go.Figure, trading_zones: pd.DataFrame, rows: list[int]):
    """Add horizontal bands for hot zones"""

    for _, zone in trading_zones.iterrows():
        color = COLORS.get(zone['risk_level'], '#888888')
        price = zone['price_level']

        for row in rows:
            fig.add_hrect(
                y0=price - 0.0005,  # ±5 pips band
                y1=price + 0.0005,
                fillcolor=color,
                opacity=0.15,
                layer='below',
                line_width=0,
                row=row,
                col=1
            )

def add_burst_highlights(fig: go.Figure, deviations: pd.DataFrame, rows: list[int]):
    """Add vertical shading for burst periods"""

    # Find burst sequences
    burst_events = deviations[deviations['is_burst']].copy()

    if len(burst_events) == 0:
        return

    # Group consecutive burst events
    burst_events['time_diff'] = burst_events['Timestamp'].diff().dt.total_seconds()
    burst_events['burst_group'] = (burst_events['time_diff'] > 10).cumsum()

    for group_id in burst_events['burst_group'].unique():
        group = burst_events[burst_events['burst_group'] == group_id]
        start_time = group['Timestamp'].min()
        end_time = group['Timestamp'].max()

        for row in rows:
            fig.add_vrect(
                x0=start_time,
                x1=end_time,
                fillcolor=COLORS['burst_bg'],
                layer='below',
                line_width=0,
                row=row,
                col=1
            )

def generate_dashboard(year: str, month: str) -> Path:
    """
    Generate interactive dashboard for one month.

    Returns:
        Path to output HTML file
    """
    month_str = f"{year}-{month}"
    logger.info(f"\n{'='*80}")
    logger.info(f"Generating Interactive Dashboard: {month_str}")
    logger.info(f"{'='*80}")

    # Load data
    viz_data = load_visualization_data(year, month)

    # Create 3-row subplot
    logger.info("\nCreating figure with 3 subplots...")
    fig = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        subplot_titles=(
            '5-Second Bars',
            '15-Second Bars',
            '1-Minute Bars'
        ),
        row_heights=[0.33, 0.33, 0.34]
    )

    # Add candlestick charts
    logger.info("Adding candlestick charts...")
    fig.add_trace(create_candlestick_trace(viz_data['ohlc_5s'], '5s'), row=1, col=1)
    fig.add_trace(create_candlestick_trace(viz_data['ohlc_15s'], '15s'), row=2, col=1)
    fig.add_trace(create_candlestick_trace(viz_data['ohlc_1m'], '1m'), row=3, col=1)

    # Add deviation markers to all panels
    logger.info("Adding deviation markers...")
    for row in [1, 2, 3]:
        add_deviation_markers(fig, viz_data['deviations'], row)

    # Add hot zone bands
    logger.info("Adding hot zone bands...")
    add_hot_zone_bands(fig, viz_data['trading_zones'], [1, 2, 3])

    # Add burst highlights
    logger.info("Adding burst period highlights...")
    add_burst_highlights(fig, viz_data['deviations'], [1, 2, 3])

    # Configure layout
    logger.info("Configuring layout...")
    metadata = viz_data['metadata']

    fig.update_layout(
        title=dict(
            text=f"EUR/USD Zero-Spread Deviations - {month_str}<br>" +
                 f"<sub>{metadata['n_deviations']:,} events | " +
                 f"{metadata['n_hot_zones']} hot zones | " +
                 f"{metadata['burst_count']} burst events ({metadata['burst_count']/metadata['n_deviations']*100:.1f}%)</sub>",
            x=0.5,
            xanchor='center'
        ),
        height=1400,
        hovermode='x unified',
        xaxis_rangeslider_visible=False,
        xaxis3_rangeslider_visible=False,
        showlegend=True,
        legend=dict(
            orientation='h',
            yanchor='bottom',
            y=1.02,
            xanchor='center',
            x=0.5
        ),
        template='plotly_white'
    )

    # Update y-axes
    fig.update_yaxes(title_text="Price (EUR/USD)", row=1, col=1)
    fig.update_yaxes(title_text="Price (EUR/USD)", row=2, col=1)
    fig.update_yaxes(title_text="Price (EUR/USD)", row=3, col=1)

    # Update x-axis
    fig.update_xaxes(title_text="Time (UTC)", row=3, col=1)

    # Save to HTML
    output_path = OUTPUT_DIR / f"eurusd_deviation_dashboard_{month_str}.html"
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
    """Execute dashboard generation"""

    import argparse
    parser = argparse.ArgumentParser(description='Generate interactive dashboard')
    parser.add_argument('--year', type=str, required=True, help='Year (e.g., 2024)')
    parser.add_argument('--month', type=str, required=True, help='Month (01-12)')

    args = parser.parse_args()

    try:
        output_path = generate_dashboard(args.year, args.month)
        logger.info(f"\n✅ Success! Dashboard saved to: {output_path}")
        logger.info(f"\nNext step: Open {output_path} in your browser")
    except Exception as e:
        logger.error(f"\n❌ Dashboard generation failed: {e}")
        raise

if __name__ == "__main__":
    main()
