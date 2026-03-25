import pandas as pd
import numpy as np
import plotly.graph_objects as go
from scipy.stats import norm
import os

# Configuration
exchange = 'kucoin'
pair = 'BTC_USDT'
base_path = f'user_data/data/{exchange}'
timeframes = ['1h', '4h', '1d', '1w']
output_file = 'user_data/plot/probability_heatmap.html'
window = 20
num_std = 4
price_grid_points = 150
lookback_candles = 300 # 1h candles to plot

def load_tf_data(tf):
    file_path = f'{base_path}/{pair}-{tf}.feather'
    if not os.path.exists(file_path):
        print(f"Warning: {file_path} not found.")
        return None
    df = pd.read_feather(file_path)
    df['date'] = pd.to_datetime(df['date'], unit='ms')

    # Calculate indicators
    df['sma'] = df['close'].rolling(window=window).mean()
    df['std'] = df['close'].rolling(window=window).std()

    return df[['date', 'sma', 'std', 'open', 'high', 'low', 'close']]

def main():
    # Load 1h data as base
    df_base = load_tf_data('1h')
    if df_base is None:
        return

    # Filter to recent data
    df_base = df_base.iloc[-lookback_candles:].reset_index(drop=True)
    dates = df_base['date']

    # Initialize probability accumulation
    # Grid covers the range of 1h data for plotting
    min_price = df_base['low'].min() * 0.95
    max_price = df_base['high'].max() * 1.05
    price_grid = np.linspace(min_price, max_price, price_grid_points)

    # cumulative_probs will store the superposed PDF
    actual_lookback = len(df_base)
    cumulative_probs = np.zeros((actual_lookback, price_grid_points))
    count_tfs = 0

    for tf in timeframes:
        df_tf = load_tf_data(tf)
        if df_tf is None:
            continue

        # Merge/Align tf data to 1h base
        # We use merge_asof to align lower resolution data to 1h timestamps
        df_merged = pd.merge_asof(
            df_base[['date']],
            df_tf[['date', 'sma', 'std']].dropna(),
            on='date',
            direction='backward'
        )

        # Calculate PDF for this timeframe at each 1h timestamp
        tf_probs = []
        valid_tf = False
        for _, row in df_merged.iterrows():
            mu = row['sma']
            sigma = row['std']

            if pd.isna(mu) or pd.isna(sigma) or sigma == 0:
                tf_probs.append(np.zeros(price_grid_points))
            else:
                probs = norm.pdf(price_grid, loc=mu, scale=sigma)
                tf_probs.append(probs)
                valid_tf = True

        if valid_tf:
            cumulative_probs += np.array(tf_probs)
            count_tfs += 1
            print(f"Added timeframe: {tf}")

    if count_tfs > 0:
        # Average the probabilities (Superposition)
        heatmap_z = (cumulative_probs / count_tfs).T
    else:
        print("No valid timeframe data found for heatmap.")
        return

    # Create figure
    fig = go.Figure()

    # 1. Add Heatmap (Superposed Probability Density)
    fig.add_trace(go.Heatmap(
        z=heatmap_z,
        x=dates,
        y=price_grid,
        colorscale='Viridis',
        opacity=0.8,
        colorbar=dict(title='Avg Prob. Density'),
        showscale=True,
        name='Superposed Prob. Heatmap'
    ))

    # 2. Add Candlesticks (Price)
    fig.add_trace(go.Candlestick(
        x=df_base['date'],
        open=df_base['open'],
        high=df_base['high'],
        low=df_base['low'],
        close=df_base['close'],
        name=f'{pair} (1h)'
    ))

    # Update layout
    fig.update_layout(
        title=f'{pair} Superposed Probability Heatmap ({", ".join(timeframes)})',
        xaxis_title='Date',
        yaxis_title='Price',
        template='plotly_dark',
        xaxis_rangeslider_visible=False,
        height=900
    )

    # Save to file
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    fig.write_html(output_file)
    print(f"Superposed heatmap saved to {output_file}")

if __name__ == "__main__":
    main()
