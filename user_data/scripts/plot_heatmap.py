import pandas as pd
import numpy as np
import plotly.graph_objects as go
from scipy.stats import norm
import os

# Configuration
input_file = 'user_data/data/kucoin/BTC_USDT-1h.feather'
output_file = 'user_data/plot/probability_heatmap.html'
window = 20
num_std = 4
price_grid_points = 100

def main():
    if not os.path.exists(input_file):
        print(f"Error: {input_file} not found.")
        return

    # Load data
    df = pd.read_feather(input_file)
    df['date'] = pd.to_datetime(df['date'], unit='ms')

    # Calculate Bollinger Band parameters
    df['sma'] = df['close'].rolling(window=window).mean()
    df['std'] = df['close'].rolling(window=window).std()

    # Drop initial rows with NaN values
    df = df.dropna().reset_index(drop=True)

    # Use the last 200 candles for better visualization
    df = df.iloc[-200:].reset_index(drop=True)

    # Generate price grid
    min_price = (df['sma'] - num_std * df['std']).min()
    max_price = (df['sma'] + num_std * df['std']).max()
    price_grid = np.linspace(min_price, max_price, price_grid_points)

    # Compute probability heatmap
    dates = df['date']
    heatmap_z = []

    for _, row in df.iterrows():
        mu = row['sma']
        sigma = row['std']
        # Probability Density Function for the price grid at this timestamp
        probs = norm.pdf(price_grid, loc=mu, scale=sigma)
        heatmap_z.append(probs)

    heatmap_z = np.array(heatmap_z).T  # Transpose to match Plotly heatmap format (y: price, x: date)

    # Create figure
    fig = go.Figure()

    # 1. Add Heatmap (Probability Density)
    fig.add_trace(go.Heatmap(
        z=heatmap_z,
        x=dates,
        y=price_grid,
        colorscale='Viridis',
        opacity=0.7,
        colorbar=dict(title='Prob. Density'),
        showscale=True,
        name='Prob. Heatmap'
    ))

    # 2. Add Candlesticks (Price)
    fig.add_trace(go.Candlestick(
        x=df['date'],
        open=df['open'],
        high=df['high'],
        low=df['low'],
        close=df['close'],
        name='BTC/USDT'
    ))

    # 3. Add Bollinger Bands Lines
    fig.add_trace(go.Scatter(
        x=df['date'],
        y=df['sma'] + 2 * df['std'],
        line=dict(color='rgba(255, 255, 255, 0.5)', width=1, dash='dash'),
        name='BB Upper (2nd std)'
    ))
    fig.add_trace(go.Scatter(
        x=df['date'],
        y=df['sma'],
        line=dict(color='rgba(255, 255, 255, 0.8)', width=1.5),
        name='SMA (20)'
    ))
    fig.add_trace(go.Scatter(
        x=df['date'],
        y=df['sma'] - 2 * df['std'],
        line=dict(color='rgba(255, 255, 255, 0.5)', width=1, dash='dash'),
        name='BB Lower (2nd std)'
    ))

    # Update layout
    fig.update_layout(
        title='BTC/USDT Probability Heatmap based on Normal Distribution & Bollinger Bands',
        xaxis_title='Date',
        yaxis_title='Price',
        template='plotly_dark',
        xaxis_rangeslider_visible=False,
        height=800
    )

    # Save to file
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    fig.write_html(output_file)
    print(f"Heatmap saved to {output_file}")

if __name__ == "__main__":
    main()
