#!/usr/bin/env python3
"""
Diagnostic script to visualize burst decay lines at different time horizons.
Generates PNG images for self-checking using Plotly.
"""

import pandas as pd
import plotly.graph_objects as go
from pathlib import Path

# Paths
DATA_DIR = Path("/tmp")
OUTPUT_DIR = Path("/tmp")

# Colors
COLORS = {
    5: '#8B00FF',  # Purple
    4: '#FF0000',  # Red
    3: '#FF8800',  # Orange
    2: '#FFD700',  # Yellow
    1: '#00CC00',  # Green
    0: '#0066FF'   # Blue
}

def create_diagnostic_plot(start_time, duration_hours, output_name):
    """
    Create diagnostic plot for specific time window using Plotly.

    Args:
        start_time: Start timestamp string (e.g., "2024-08-05 07:25:00")
        duration_hours: How many hours to show
        output_name: Output filename
    """
    print(f"\n{'='*60}")
    print(f"Creating diagnostic plot: {output_name}")
    print(f"Time window: {start_time} + {duration_hours}h")
    print(f"{'='*60}")

    # Load data
    ohlc = pd.read_parquet(DATA_DIR / "viz_2024-08_ohlc_1m.parquet")
    deviations = pd.read_parquet(DATA_DIR / "viz_2024-08_deviations.parquet")

    # Convert start_time to datetime
    start_dt = pd.to_datetime(start_time, utc=True)
    end_dt = start_dt + pd.Timedelta(hours=duration_hours)

    # Filter to time window
    ohlc_window = ohlc[(ohlc['Timestamp'] >= start_dt) & (ohlc['Timestamp'] <= end_dt)]
    dev_window = deviations[(deviations['Timestamp'] >= start_dt) & (deviations['Timestamp'] <= end_dt)]

    print(f"  OHLC bars in window: {len(ohlc_window)}")
    print(f"  Deviations in window: {len(dev_window)}")

    # Find bursts in this window
    bursts = dev_window[dev_window['is_burst']]
    print(f"  Burst events in window: {len(bursts)}")

    if len(bursts) == 0:
        print("  WARNING: No burst events in this window!")
        # Still create plot showing deviations
        bursts = pd.DataFrame()  # Empty

    # Create figure
    fig = go.Figure()

    # Add price line
    fig.add_trace(go.Scatter(
        x=ohlc_window['Timestamp'],
        y=ohlc_window['close'],
        mode='lines',
        line=dict(color='#D0D0D0', width=1),
        name='Price',
        opacity=0.5
    ))

    # Add deviation markers
    for risk_level in [4, 3, 2, 1, 0]:
        subset = dev_window[dev_window['risk_level'] == risk_level]
        if len(subset) > 0:
            fig.add_trace(go.Scatter(
                x=subset['Timestamp'],
                y=subset['price'],
                mode='markers',
                marker=dict(color=COLORS[risk_level], size=8),
                name=f'Level {risk_level} ({len(subset)})'
            ))

    # Add burst decay lines (sample to max 10 for clarity)
    if len(bursts) > 0:
        if len(bursts) > 10:
            bursts_sampled = bursts.sample(n=10, random_state=42)
            print(f"\n  Sampled 10 of {len(bursts)} bursts for clarity")
        else:
            bursts_sampled = bursts

        decay_duration = pd.Timedelta('30min')
        n_segments = 5

        print(f"\n  Drawing decay lines for {len(bursts_sampled)} bursts:")
        for idx, (_, burst) in enumerate(bursts_sampled.iterrows()):
            color = COLORS[burst['risk_level']]
            start_time_burst = burst['Timestamp']
            price = burst['price']

            print(f"    Burst {idx+1}: {start_time_burst}, price={price:.5f}, risk={burst['risk_level']}")

            # Draw fading segments using add_shape
            for i in range(n_segments):
                seg_start = start_time_burst + (i * decay_duration / n_segments)
                seg_end = start_time_burst + ((i + 1) * decay_duration / n_segments)
                opacity = 0.6 * (1 - i / n_segments)

                fig.add_shape(
                    type="line",
                    x0=seg_start,
                    y0=price,
                    x1=seg_end,
                    y1=price,
                    line_color=color,
                    line_width=4,
                    opacity=opacity,
                    layer="above"
                )

    # Update layout
    fig.update_layout(
        title=f'Burst Decay Diagnostic - {duration_hours}h window<br>'
              f'<sub>{len(dev_window)} deviations, {len(bursts)} bursts, 30-min decay trails</sub>',
        xaxis_title='Time (UTC)',
        yaxis_title='Price (EUR/USD)',
        height=600,
        template='plotly_white',
        showlegend=True
    )

    # Save as HTML (faster than PNG)
    output_path = OUTPUT_DIR / output_name.replace('.png', '.html')
    fig.write_html(str(output_path))
    print(f"\n  ✓ Saved: {output_path}")

    return output_path

def main():
    """Generate 3 diagnostic plots at different time scales"""

    print("\n" + "="*60)
    print("BURST DECAY DIAGNOSTIC - 3 Time Horizons")
    print("="*60)

    # Horizon 1: 15 minutes (ultra-zoom)
    path1 = create_diagnostic_plot(
        start_time="2024-08-05 07:25:00",
        duration_hours=0.25,  # 15 minutes
        output_name="diagnostic_burst_15min.png"
    )

    # Horizon 2: 1 hour (medium zoom)
    path2 = create_diagnostic_plot(
        start_time="2024-08-05 07:00:00",
        duration_hours=1.0,
        output_name="diagnostic_burst_1hour.png"
    )

    # Horizon 3: 4 hours (broader view)
    path3 = create_diagnostic_plot(
        start_time="2024-08-05 06:00:00",
        duration_hours=4.0,
        output_name="diagnostic_burst_4hour.png"
    )

    print("\n" + "="*60)
    print("✅ All diagnostic plots generated!")
    print("="*60)
    print(f"\nView images at:")
    print(f"  1. {path1}")
    print(f"  2. {path2}")
    print(f"  3. {path3}")

if __name__ == "__main__":
    main()
