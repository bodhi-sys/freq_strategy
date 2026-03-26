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

def get_line_params(p1_idx, p1_val, p2_idx, p2_val):
    slope = (p2_val - p1_val) / (p2_idx - p1_idx)
    intercept = p1_val - slope * p1_idx
    return slope, intercept

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
            idx1, _, p1 = last_5[0]; idx2, _, p2 = last_5[1]; idx3, _, p3 = last_5[2]; idx4, _, p4 = last_5[3]; idx5, _, p5 = last_5[4]
            if p3 < p1 and p4 < p2 and p4 > p1 and p5 < p3:
                bullish_patterns.append(last_5)

        # Bearish
        if last_5[0][1] == 'peak' and last_5[1][1] == 'valley' and \
           last_5[2][1] == 'peak' and last_5[3][1] == 'valley' and \
           last_5[4][1] == 'peak':
            idx1, _, p1 = last_5[0]; idx2, _, p2 = last_5[1]; idx3, _, p3 = last_5[2]; idx4, _, p4 = last_5[3]; idx5, _, p5 = last_5[4]
            if p3 > p1 and p4 > p2 and p4 < p1 and p5 > p3:
                bearish_patterns.append(last_5)

    fig = go.Figure()

    # 1. Candlesticks
    fig.add_trace(go.Candlestick(
        x=df['date'], open=df['open'], high=df['high'], low=df['low'], close=df['close'], name=pair
    ))

    # 2. ZigZag Line
    zz_dates = [df.iloc[p[0]]['date'] for p in pivots]
    zz_prices = [p[2] for p in pivots]
    fig.add_trace(go.Scatter(
        x=zz_dates, y=zz_prices, mode='lines+markers',
        line=dict(color='yellow', width=1), marker=dict(size=4, color='white'), name='ZigZag'
    ))

    # 3. Wolfe Patterns & EPA/ETA lines
    for i, pattern in enumerate(bullish_patterns + bearish_patterns):
        is_bullish = pattern[0][1] == 'valley'
        color = 'cyan' if is_bullish else 'orange'

        idx1, _, p1 = pattern[0]; idx2, _, p2 = pattern[1]; idx3, _, p3 = pattern[2]; idx4, _, p4 = pattern[3]; idx5, _, p5 = pattern[4]

        # Line 1-3
        m13, c13 = get_line_params(idx1, p1, idx3, p3)
        # Line 2-4
        m24, c24 = get_line_params(idx2, p2, idx4, p4)
        # Line 1-4 (EPA Line)
        m14, c14 = get_line_params(idx1, p1, idx4, p4)

        # ETA (Intersection of 1-3 and 2-4)
        # m13 * x + c13 = m24 * x + c24 => x = (c24 - c13) / (m13 - m24)
        if (m13 - m24) != 0:
            eta_idx = (c24 - c13) / (m13 - m24)
            epa_price = m14 * eta_idx + c14

            # Draw Lines 1-3 and 2-4 to ETA
            max_idx = max(len(df)-1, int(eta_idx) + 10)

            # We can't easily plot past df range dates, so we use indices for projection
            # but for visualization we'll stop at max(df_index, eta_idx)

            def get_date(idx):
                if idx < len(df): return df.iloc[int(idx)]['date']
                # Extrapolate date
                last_date = df.iloc[-1]['date']
                delta = df.iloc[-1]['date'] - df.iloc[-2]['date']
                return last_date + delta * (idx - (len(df)-1))

            eta_date = get_date(eta_idx)

            # Plot 1-3
            fig.add_trace(go.Scatter(
                x=[df.iloc[idx1]['date'], eta_date], y=[p1, m13 * eta_idx + c13],
                mode='lines', line=dict(color='gray', width=1, dash='dash'), name=f'1-3 Line {i+1}'
            ))
            # Plot 2-4
            fig.add_trace(go.Scatter(
                x=[df.iloc[idx2]['date'], eta_date], y=[p2, m24 * eta_idx + c24],
                mode='lines', line=dict(color='gray', width=1, dash='dash'), name=f'2-4 Line {i+1}'
            ))
            # Plot EPA Line (1-4 extended)
            fig.add_trace(go.Scatter(
                x=[df.iloc[idx1]['date'], eta_date], y=[p1, epa_price],
                mode='lines', line=dict(color=color, width=2), name=f'EPA Line {i+1}'
            ))

            # Mark EPA/ETA Target
            fig.add_trace(go.Scatter(
                x=[eta_date], y=[epa_price],
                mode='markers', marker=dict(color=color, size=10, symbol='x'),
                name=f'EPA Target {i+1}'
            ))

            fig.add_annotation(
                x=eta_date, y=epa_price, text=f"EPA Target: {epa_price:.2f}",
                showarrow=True, arrowhead=1, font=dict(color=color)
            )

        # Highlight points
        for j, p in enumerate(pattern):
            fig.add_annotation(
                x=df.iloc[p[0]]['date'], y=p[2], text=str(j+1),
                showarrow=True, arrowhead=1, font=dict(color=color),
                ax=0, ay=-20 if p[1] == 'peak' else 20
            )

    fig.update_layout(
        title=f'Wolfe Waves Pattern with EPA/ETA Projections - {pair}',
        xaxis_title='Date', yaxis_title='Price', template='plotly_dark',
        xaxis_rangeslider_visible=False, height=800
    )

    fig.write_html(output_file)
    print(f"Wolfe Waves chart saved to {output_file}")

if __name__ == "__main__":
    main()
