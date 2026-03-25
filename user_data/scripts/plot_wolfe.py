import pandas as pd
import numpy as np
import plotly.graph_objects as go
import os

# Configuration
exchange = 'kucoin'
pair = 'BTC_USDT'
input_file = f'user_data/data/{exchange}/{pair}-1h.feather'
output_file = 'user_data/plot/wolfe_waves_chart.html'
lookback_candles = 500

def find_pivots(dataframe, depth=12):
    pivots = []
    for i in range(2 * depth, len(dataframe)):
        candidate_idx = dataframe.index[i-depth]
        window = dataframe.iloc[i-2*depth : i+1]

        if dataframe.iloc[i-depth]['low'] == window['low'].min():
            pivots.append((candidate_idx, 'valley', dataframe.iloc[i-depth]['low']))

        if dataframe.iloc[i-depth]['high'] == window['high'].max():
            pivots.append((candidate_idx, 'peak', dataframe.iloc[i-depth]['high']))

    clean_pivots = []
    for p in pivots:
        if not clean_pivots:
            clean_pivots.append(p)
            continue
        if p[0] == clean_pivots[-1][0]: continue
        if p[1] == clean_pivots[-1][1]:
            if p[1] == 'valley':
                if p[2] < clean_pivots[-1][2]: clean_pivots[-1] = p
            else:
                if p[2] > clean_pivots[-1][2]: clean_pivots[-1] = p
        else:
            clean_pivots.append(p)
    return clean_pivots

def main():
    if not os.path.exists(input_file):
        print(f"Error: {input_file} not found.")
        return

    df = pd.read_feather(input_file)
    df['date'] = pd.to_datetime(df['date'], unit='ms')
    df = df.iloc[-lookback_candles:].reset_index(drop=True)

    pivots = find_pivots(df)

    # Identify patterns
    bullish_patterns = []
    bearish_patterns = []
    for i in range(4, len(pivots)):
        last_5 = pivots[i-4:i+1]

        # Bullish
        if last_5[0][1] == 'valley' and last_5[1][1] == 'peak' and \
           last_5[2][1] == 'valley' and last_5[3][1] == 'peak' and \
           last_5[4][1] == 'valley':
            idx1, _, p1 = last_5[0]
            idx2, _, p2 = last_5[1]
            idx3, _, p3 = last_5[2]
            idx4, _, p4 = last_5[3]
            idx5, _, p5 = last_5[4]
            if p3 < p1 and p4 < p2 and p4 > p1 and p5 < p3:
                bullish_patterns.append(last_5)

        # Bearish
        if last_5[0][1] == 'peak' and last_5[1][1] == 'valley' and \
           last_5[2][1] == 'peak' and last_5[3][1] == 'valley' and \
           last_5[4][1] == 'peak':
            idx1, _, p1 = last_5[0]
            idx2, _, p2 = last_5[1]
            idx3, _, p3 = last_5[2]
            idx4, _, p4 = last_5[3]
            idx5, _, p5 = last_5[4]
            if p3 > p1 and p4 > p2 and p4 < p1 and p5 > p3:
                bearish_patterns.append(last_5)

    # Create figure
    fig = go.Figure()

    # 1. Candlesticks
    fig.add_trace(go.Candlestick(
        x=df['date'],
        open=df['open'], high=df['high'], low=df['low'], close=df['close'],
        name=pair
    ))

    # 2. ZigZag Line
    zz_dates = [df.iloc[p[0]]['date'] for p in pivots]
    zz_prices = [p[2] for p in pivots]
    fig.add_trace(go.Scatter(
        x=zz_dates, y=zz_prices,
        mode='lines+markers',
        line=dict(color='yellow', width=1),
        marker=dict(size=4, color='white'),
        name='ZigZag'
    ))

    # 3. Wolfe Patterns & EPA lines
    for i, pattern in enumerate(bullish_patterns + bearish_patterns):
        is_bullish = pattern[0][1] == 'valley'
        color = 'cyan' if is_bullish else 'orange'

        p1_idx, _, p1_price = pattern[0]
        p4_idx, _, p4_price = pattern[3]

        p1_date = df.iloc[p1_idx]['date']
        p4_date = df.iloc[p4_idx]['date']

        # EPA Line
        dx = p4_idx - p1_idx
        dy = p4_price - p1_price
        if dx == 0: continue
        slope = dy / dx
        extend_dx = (len(df) - 1) - p1_idx
        epa_end_price = p1_price + slope * extend_dx
        epa_end_date = df.iloc[-1]['date']

        fig.add_trace(go.Scatter(
            x=[p1_date, epa_end_date],
            y=[p1_price, epa_end_price],
            mode='lines',
            line=dict(color=color, width=2, dash='dot'),
            name=f'{"Bull" if is_bullish else "Bear"} EPA {i+1}'
        ))

        # Highlight points
        for j, p in enumerate(pattern):
            fig.add_annotation(
                x=df.iloc[p[0]]['date'],
                y=p[2],
                text=str(j+1),
                showarrow=True,
                arrowhead=1,
                font=dict(color=color),
                ax=0, ay=-20 if p[1] == 'peak' else 20
            )

    fig.update_layout(
        title=f'Wolfe Waves Pattern (Long & Short) Visualization - {pair}',
        xaxis_title='Date',
        yaxis_title='Price',
        template='plotly_dark',
        xaxis_rangeslider_visible=False,
        height=800
    )

    fig.write_html(output_file)
    print(f"Wolfe Waves chart saved to {output_file}")

if __name__ == "__main__":
    main()
