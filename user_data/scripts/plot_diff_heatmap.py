import pandas as pd
import numpy as np
import plotly.graph_objects as go
from scipy.stats import norm
import os

# Configuration
exchange = 'gate'
pair = 'BTC_USDT_USDT'
base_path = f'user_data/data/{exchange}/futures'
timeframes = {
    '1h': 1,
    '4h': 4,
    '1d': 24,
    '1w': 168
}
output_file = 'user_data/plot/diff_heatmap.html'
window = 20
num_std = 4
grid_points = 150
lookback_candles = 300 # 1h candles to plot

def load_tf_diff_data(tf, hours):
    file_path = f'{base_path}/{pair}-{tf}-futures.feather'
    if not os.path.exists(file_path):
        print(f"Warning: {file_path} not found.")
        return None
    df = pd.read_feather(file_path)
    df['date'] = pd.to_datetime(df['date'], unit='ms')

    # Calculate price difference (current - prev)
    df['diff'] = df['close'].diff()

    # Normalize to "change per hour" to make timeframes comparable
    df['diff_h'] = df['diff'] / hours

    # Calculate indicators on normalized differences
    df['sma_h'] = df['diff_h'].rolling(window=window).mean()
    df['std_h'] = df['diff_h'].rolling(window=window).std()

    return df[['date', 'sma_h', 'std_h', 'diff_h']]

def main():
    # Load 1h data as base for timestamps and plotting
    df_base = load_tf_diff_data('1h', 1)
    if df_base is None:
        return

    # Filter to recent data
    df_base = df_base.iloc[-lookback_candles:].reset_index(drop=True)
    dates = df_base['date']

    # Initialize probability accumulation
    # Grid covers the range of 1h normalized differences
    min_diff = df_base['diff_h'].min() * 1.5
    max_diff = df_base['diff_h'].max() * 1.5
    diff_grid = np.linspace(min_diff, max_diff, grid_points)

    # cumulative_probs will store the superposed PDF
    actual_lookback = len(df_base)
    cumulative_probs = np.zeros((actual_lookback, grid_points))
    count_tfs = 0

    for tf, hours in timeframes.items():
        df_tf = load_tf_diff_data(tf, hours)
        if df_tf is None:
            continue

        # Merge/Align tf data to 1h base
        df_merged = pd.merge_asof(
            df_base[['date']],
            df_tf[['date', 'sma_h', 'std_h']].dropna(),
            on='date',
            direction='backward'
        )

        # Calculate PDF for this timeframe's normalized difference at each 1h timestamp
        tf_probs = []
        valid_tf = False
        for _, row in df_merged.iterrows():
            mu = row['sma_h']
            sigma = row['std_h']

            if pd.isna(mu) or pd.isna(sigma) or sigma == 0:
                tf_probs.append(np.zeros(grid_points))
            else:
                probs = norm.pdf(diff_grid, loc=mu, scale=sigma)
                tf_probs.append(probs)
                valid_tf = True

        if valid_tf:
            cumulative_probs += np.array(tf_probs)
            count_tfs += 1
            print(f"Added timeframe: {tf} (normalized to 1h)")

    if count_tfs > 0:
        # Average the probabilities (Superposition)
        heatmap_z = (cumulative_probs / count_tfs).T
    else:
        print("No valid timeframe data found for heatmap.")
        return

    # Create figure
    fig = go.Figure()

    # 1. Add Heatmap (Superposed Probability Density of Price Change per Hour)
    fig.add_trace(go.Heatmap(
        z=heatmap_z,
        x=dates,
        y=diff_grid,
        colorscale='Hot',
        opacity=0.8,
        colorbar=dict(title='Avg Prob. Density'),
        showscale=True,
        name='Superposed Diff Prob. Heatmap'
    ))

    # 2. Add Line for Actual 1h Price Change
    fig.add_trace(go.Scatter(
        x=df_base['date'],
        y=df_base['diff_h'],
        mode='lines',
        line=dict(color='cyan', width=2),
        name='Actual 1h Price Change'
    ))

    # Update layout
    fig.update_layout(
        title=f'{pair} Superposed Probability Heatmap of Price Change per Hour ({", ".join(timeframes.keys())})',
        xaxis_title='Date',
        yaxis_title='Price Change per Hour (USDT)',
        template='plotly_dark',
        xaxis_rangeslider_visible=False,
        height=900
    )

    # Save to file
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    fig.write_html(output_file)
    print(f"Superposed diff heatmap saved to {output_file}")

if __name__ == "__main__":
    main()
