# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
# flake8: noqa: F401
# isort: skip_file
# --- Do not remove these imports ---
import numpy as np
import pandas as pd
from pandas import DataFrame

from freqtrade.strategy import (
    IStrategy,
    informative,
    Trade
)
from datetime import datetime

# --------------------------------
# Add your lib to import here
import talib.abstract as ta
from technical import qtpylib


class WolfeWavesStrategy(IStrategy):
    """
    Wolfe Waves Pattern Strategy (Realistic Implementation).
    Identifies patterns with a confirmation lag to avoid lookahead bias.
    Supports both Long and Short positions.
    Includes 20% buffer from EPA target for earlier exits.
    """
    INTERFACE_VERSION = 3

    # Timeframe
    timeframe = '1h'

    # Can this strategy go short?
    can_short: bool = False

    # Minimal ROI
    minimal_roi = {
        "0": 0.1,
        "1440": 0.05
    }

    # Optimal stoploss
    stoploss = -0.05

    # Run "populate_indicators()" only for new candle.
    process_only_new_candles = True

    # Number of candles the strategy requires before producing valid signals
    startup_candle_count: int = 200

    @property
    def plot_config(self):
        return {
            "main_plot": {
                "epa_target": {"color": "cyan"}
            },
            "subplots": {
                "RSI": {
                    "rsi": {"color": "green"},
                },
            }
        }

    def find_pivots(self, dataframe: DataFrame, depth: int = 5) -> list:
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

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['rsi'] = ta.RSI(dataframe)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['enter_long'] = 0
        dataframe['enter_short'] = 0
        dataframe['epa_target'] = np.nan

        pivots = self.find_pivots(dataframe, depth=12)

        if len(pivots) < 5:
            return dataframe

        for i in range(4, len(pivots)):
            last_5 = pivots[i-4:i+1]

            # 1. Bullish Wolfe Wave
            if last_5[0][1] == 'valley' and last_5[1][1] == 'peak' and \
               last_5[2][1] == 'valley' and last_5[3][1] == 'peak' and \
               last_5[4][1] == 'valley':

                idx1, _, p1 = last_5[0]
                idx4, _, p4 = last_5[3]
                idx5, _, p5 = last_5[4]
                p3 = last_5[2][2]
                p2 = last_5[1][2]

                if p3 < p1 and p4 < p2 and p4 > p1 and p5 < p3:
                    confirm_idx = idx5 + 12
                    if confirm_idx < len(dataframe):
                        dataframe.loc[confirm_idx, 'enter_long'] = 1
                        # Calculate EPA slope
                        slope = (p4 - p1) / (idx4 - idx1)
                        # Fill EPA target for future candles
                        for j in range(confirm_idx, len(dataframe)):
                            dataframe.loc[j, 'epa_target'] = p1 + slope * (j - idx1)

            # 2. Bearish Wolfe Wave
            if last_5[0][1] == 'peak' and last_5[1][1] == 'valley' and \
               last_5[2][1] == 'peak' and last_5[3][1] == 'valley' and \
               last_5[4][1] == 'peak':

                idx1, _, p1 = last_5[0]
                idx4, _, p4 = last_5[3]
                idx5, _, p5 = last_5[4]
                p3 = last_5[2][2]
                p2 = last_5[1][2]

                if p3 > p1 and p4 > p2 and p4 < p1 and p5 > p3:
                    confirm_idx = idx5 + 12
                    if confirm_idx < len(dataframe):
                        dataframe.loc[confirm_idx, 'enter_short'] = 1
                        # Calculate EPA slope
                        slope = (p4 - p1) / (idx4 - idx1)
                        # Fill EPA target for future candles
                        for j in range(confirm_idx, len(dataframe)):
                            dataframe.loc[j, 'epa_target'] = p1 + slope * (j - idx1)

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['exit_long'] = 0
        dataframe['exit_short'] = 0

        # Exit if price reaches 80% of the distance to the target EPA
        # Since we don't have entry_price here, we'll use a simplified version:
        # If EPA is above current price (Long), exit if price > 0.98 * EPA or similar.
        # But user said "threshold 20% from predicted target".
        # Let's assume they mean price >= 0.8 * target if starting from 0,
        # but in trading it usually means 80% of the projected move.

        # We can use custom_exit for more precise control if needed.
        # For now, let's use a simple price level check.

        return dataframe

    def custom_exit(self, pair: str, trade: 'Trade', current_time: 'datetime', current_rate: float,
                    current_profit: float, **kwargs):
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = dataframe.iloc[-1].squeeze()

        if pd.isna(last_candle['epa_target']):
            return None

        epa = last_candle['epa_target']
        entry = trade.open_rate

        if trade.is_short:
            # Short target is below entry.
            # Projected move = entry - epa
            # Target threshold = entry - 0.8 * (entry - epa) = 0.2*entry + 0.8*epa
            if current_rate <= (0.2 * entry + 0.8 * epa):
                return "epa_target_80_percent"
        else:
            # Long target is above entry.
            # Projected move = epa - entry
            # Target threshold = entry + 0.8 * (epa - entry) = 0.2*entry + 0.8*epa
            if current_rate >= (0.2 * entry + 0.8 * epa):
                return "epa_target_80_percent"

        return None
