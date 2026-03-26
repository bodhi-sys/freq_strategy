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
    fig.add_trace(go.Candlestick(x=df['date'], open=df['open'], high=df['high'], low=df['low'], close=df['close'], name=pair))

    def get_date(idx):
        if idx < len(df): return df.iloc[int(idx)]['date']
        last_date = df.iloc[-1]['date']
        delta = df.iloc[-1]['date'] - df.iloc[-2]['date']
        return last_date + delta * (idx - (len(df)-1))

    for i, pattern in enumerate(bullish_patterns + bearish_patterns):
        is_bullish = pattern[0][1] == 'valley'
        color = 'cyan' if is_bullish else 'orange'
        idx1, _, p1 = pattern[0]; idx3, _, p3 = pattern[2]; idx4, _, p4 = pattern[3]; idx5, _, p5 = pattern[4]

        # Line A: EPA (1-4)
        mA, cA = get_line_params(idx1, p1, idx4, p4)
        # Line B: Parallel to 3-4 through P5
        mB, _ = get_line_params(idx3, p3, idx4, p4)
        cB = p5 - mB * idx5

        if (mA - mB) != 0:
            target_idx = (cB - cA) / (mA - mB)
            target_price = mA * target_idx + cA
            target_date = get_date(target_idx)

            # Plot EPA Line
            fig.add_trace(go.Scatter(x=[df.iloc[idx1]['date'], target_date], y=[p1, target_price],
                mode='lines', line=dict(color=color, width=2), name=f'EPA Line {i+1}'))
            # Plot Parallel Line from P5
            fig.add_trace(go.Scatter(x=[df.iloc[idx5]['date'], target_date], y=[p5, target_price],
                mode='lines', line=dict(color='magenta', width=1, dash='dot'), name=f'P5 Parallel {i+1}'))

            # Mark Target
            fig.add_trace(go.Scatter(x=[target_date], y=[target_price],
                mode='markers', marker=dict(color=color, size=10, symbol='star'), name=f'Target {i+1}'))

            # Mark 80% Exit Threshold
            exit_price = 0.2 * p5 + 0.8 * target_price
            fig.add_trace(go.Scatter(x=[df.iloc[idx5]['date'], target_date], y=[exit_price, exit_price],
                mode='lines', line=dict(color='yellow', width=1, dash='dash'), name=f'80% Exit {i+1}'))

        for j, p in enumerate(pattern):
            fig.add_annotation(x=df.iloc[p[0]]['date'], y=p[2], text=str(j+1), showarrow=True, arrowhead=1, font=dict(color=color), ax=0, ay=-20 if p[1] == 'peak' else 20)

    fig.update_layout(title=f'Wolfe Waves Geometric Target Projections - {pair}', xaxis_title='Date', yaxis_title='Price', template='plotly_dark', xaxis_rangeslider_visible=False, height=800)
    fig.write_html(output_file)
    print(f"Wolfe Waves chart saved to {output_file}")

if __name__ == "__main__":
    main()
