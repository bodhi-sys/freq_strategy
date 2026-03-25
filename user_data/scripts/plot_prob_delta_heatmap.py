import pandas as pd
import numpy as np
import plotly.graph_objects as go
from scipy.stats import norm
import os

# Configuration
exchange = 'gate'
pair = 'BTC_USDT_USDT'
base_path = f'user_data/data/{exchange}/futures'
timeframes = ['1h', '4h', '1d', '1w']
output_file = 'user_data/plot/prob_delta_heatmap.html'
window = 20
num_std = 4
price_grid_points = 150
lookback_candles = 300 # 1h candles to plot

def load_tf_data(tf):
    file_path = f'{base_path}/{pair}-{tf}-futures.feather'
    if not os.path.exists(file_path):
        print(f"Warning: {file_path} not found.")
        return None
    df = pd.read_feather(file_path)
    df['date'] = pd.to_datetime(df['date'], unit='ms')

    # Calculate Bollinger Band parameters
    df['sma'] = df['close'].rolling(window=window).mean()
    df['std'] = df['close'].rolling(window=window).std()

    return df[['date', 'sma', 'std', 'open', 'high', 'low', 'close']]

def main():
    # Load 1h data as base. We need more than lookback_candles to calculate delta for the first plotted candle.
    df_full = load_tf_data('1h')
    if df_full is None:
        return

    # Filter to lookback + 1 for delta calculation
    df_base = df_full.iloc[-(lookback_candles + 1):].reset_index(drop=True)

    # Initialize grid covering the range of 1h data
    min_price = df_base['low'].min() * 0.95
    max_price = df_base['high'].max() * 1.05
    price_grid = np.linspace(min_price, max_price, price_grid_points)

    # cumulative_probs will store the superposed PDF matrix (Time x Price)
    actual_rows = len(df_base)
    cumulative_probs = np.zeros((actual_rows, price_grid_points))
    count_tfs = 0

    for tf in timeframes:
        df_tf = load_tf_data(tf)
        if df_tf is None:
            continue

        # Merge/Align tf indicators to 1h base
        df_merged = pd.merge_asof(
            df_base[['date']],
            df_tf[['date', 'sma', 'std']].dropna(),
            on='date',
            direction='backward'
        )

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
        avg_probs = cumulative_probs / count_tfs
        # Calculate Delta: Prob(t) - Prob(t-1) for each price level
        # Axis 0 is Time
        delta_probs = np.diff(avg_probs, axis=0)

        # heatmap_z is Transposed for Plotly (y: price, x: date)
        heatmap_z = delta_probs.T
        dates = df_base['date'].iloc[1:] # Align to diff'd rows
        plot_df = df_base.iloc[1:]
    else:
        print("No valid timeframe data found for heatmap.")
        return

    # Create figure
    fig = go.Figure()

    # 1. Add Heatmap (Superposed Probability Delta: Prob(t) - Prob(t-1))
    fig.add_trace(go.Heatmap(
        z=heatmap_z,
        x=dates,
        y=price_grid,
        colorscale='RdBu', # Red for increase, Blue for decrease
        zmid=0,
        opacity=0.8,
        colorbar=dict(title='Prob. Delta'),
        showscale=True,
        name='Prob. Delta Heatmap'
    ))

    # 2. Add Candlesticks (Price)
    fig.add_trace(go.Candlestick(
        x=plot_df['date'],
        open=plot_df['open'],
        high=plot_df['high'],
        low=plot_df['low'],
        close=plot_df['close'],
        name=f'{pair} (1h)'
    ))

    # Update layout
    fig.update_layout(
        title=f'{pair} Probability Delta Heatmap ({", ".join(timeframes)})',
        xaxis_title='Date',
        yaxis_title='Price',
        template='plotly_dark',
        xaxis_rangeslider_visible=False,
        height=900
    )

    # Save to file
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    fig.write_html(output_file)
    print(f"Probability delta heatmap saved to {output_file}")

if __name__ == "__main__":
    main()
