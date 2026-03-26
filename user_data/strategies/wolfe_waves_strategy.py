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
    Target Price: Intersection of EPA (1-4) and Parallel to (3-4) through P5.
    Exit: 80% of path from P5 to Target.
    """
    INTERFACE_VERSION = 3

    # Timeframe
    timeframe = '1h'

    # Can this strategy go short?
    # Set to False for spot markets. Change to True for futures.
    can_short: bool = False

    # Minimal ROI
    minimal_roi = {
        "0": 0.2,
        "1440": 0.1
    }

    # Optimal stoploss
    stoploss = -0.10

    # Run "populate_indicators()" only for new candle.
    process_only_new_candles = True

    # Number of candles the strategy requires before producing valid signals
    startup_candle_count: int = 200

    @property
    def plot_config(self):
        return {
            "main_plot": {
                "target_price": {"color": "cyan"},
                "p5_price": {"color": "magenta"}
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

        # Initialize columns
        dataframe['target_price'] = np.nan
        dataframe['p5_price'] = np.nan
        dataframe['wave_type'] = 0 # 1 for bull, -1 for bear

        pivots = self.find_pivots(dataframe, depth=12)

        if len(pivots) >= 5:
            for i in range(4, len(pivots)):
                last_5 = pivots[i-4:i+1]
                idx1, _, p1 = last_5[0]
                idx2, _, p2 = last_5[1]
                idx3, _, p3 = last_5[2]
                idx4, _, p4 = last_5[3]
                idx5, _, p5 = last_5[4]

                # Bullish Wolfe Wave
                if last_5[0][1] == 'valley' and last_5[1][1] == 'peak' and \
                   last_5[2][1] == 'valley' and last_5[3][1] == 'peak' and \
                   last_5[4][1] == 'valley':
                    if p3 < p1 and p4 < p2 and p4 > p1 and p5 < p3:
                        confirm_idx = idx5 + 12
                        if confirm_idx < len(dataframe):
                            mA = (p4 - p1) / (idx4 - idx1)
                            cA = p1 - mA * idx1
                            mB = (p4 - p3) / (idx4 - idx3)
                            cB = p5 - mB * idx5
                            if (mA - mB) != 0:
                                target_idx = (cB - cA) / (mA - mB)
                                target_price = mA * target_idx + cA
                                dataframe.loc[confirm_idx, 'target_price'] = target_price
                                dataframe.loc[confirm_idx, 'p5_price'] = p5
                                dataframe.loc[confirm_idx, 'wave_type'] = 1

                # Bearish Wolfe Wave
                if last_5[0][1] == 'peak' and last_5[1][1] == 'valley' and \
                   last_5[2][1] == 'peak' and last_5[3][1] == 'valley' and \
                   last_5[4][1] == 'peak':
                    if p3 > p1 and p4 > p2 and p4 < p1 and p5 > p3:
                        confirm_idx = idx5 + 12
                        if confirm_idx < len(dataframe):
                            mA = (p4 - p1) / (idx4 - idx1)
                            cA = p1 - mA * idx1
                            mB = (p4 - p3) / (idx4 - idx3)
                            cB = p5 - mB * idx5
                            if (mA - mB) != 0:
                                target_idx = (cB - cA) / (mA - mB)
                                target_price = mA * target_idx + cA
                                dataframe.loc[confirm_idx, 'target_price'] = target_price
                                dataframe.loc[confirm_idx, 'p5_price'] = p5
                                dataframe.loc[confirm_idx, 'wave_type'] = -1

        # Forward fill to keep targets active during trades
        dataframe['target_price'] = dataframe['target_price'].ffill()
        dataframe['p5_price'] = dataframe['p5_price'].ffill()
        dataframe['wave_type'] = dataframe['wave_type'].ffill()

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['enter_long'] = 0
        dataframe['enter_short'] = 0

        # Trigger entry on calculation candle
        dataframe.loc[
            (dataframe['target_price'].notna()) &
            (dataframe['target_price'].shift(1).isna()) &
            (dataframe['wave_type'] == 1),
            'enter_long'
        ] = 1

        dataframe.loc[
            (dataframe['target_price'].notna()) &
            (dataframe['target_price'].shift(1).isna()) &
            (dataframe['wave_type'] == -1),
            'enter_short'
        ] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['exit_long'] = 0
        dataframe['exit_short'] = 0
        return dataframe

    def custom_exit(self, pair: str, trade: 'Trade', current_time: 'datetime', current_rate: float,
                    current_profit: float, **kwargs):
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        # Find the row for the current_time
        row = dataframe.loc[dataframe['date'] == current_time]
        if row.empty:
            return None

        last_candle = row.squeeze()

        if pd.isna(last_candle['target_price']) or pd.isna(last_candle['p5_price']):
            return None

        target = last_candle['target_price']
        p5 = last_candle['p5_price']

        # Exit threshold = p5 + 0.8 * (target - p5) = 0.2 * p5 + 0.8 * target
        threshold = (0.2 * p5 + 0.8 * target)

        if trade.is_short:
            if current_rate <= threshold:
                return "geometry_target_80_percent"
        else:
            if current_rate >= threshold:
                return "geometry_target_80_percent"

        return None
