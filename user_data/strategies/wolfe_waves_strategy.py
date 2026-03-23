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
)

# --------------------------------
# Add your lib to import here
import talib.abstract as ta
from technical import qtpylib


class WolfeWavesStrategy(IStrategy):
    """
    Wolfe Waves Pattern Strategy (Realistic Implementation).
    Identifies patterns with a confirmation lag to avoid lookahead bias.
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

    def find_pivots(self, dataframe: DataFrame, depth: int = 5) -> list:
        """
        Finds local peaks and valleys without lookahead bias.
        A pivot is confirmed when price moves away from it for 'depth' candles.
        """
        pivots = []
        for i in range(2 * depth, len(dataframe)):
            # Look at a window around the potential pivot point
            # Point at i-depth is our candidate
            candidate_idx = dataframe.index[i-depth]
            window = dataframe.iloc[i-2*depth : i+1]

            # Valley at candidate_idx if it's the lowest in the window
            if dataframe.iloc[i-depth]['low'] == window['low'].min():
                pivots.append((candidate_idx, 'valley', dataframe.iloc[i-depth]['low']))

            # Peak at candidate_idx if it's the highest in the window
            if dataframe.iloc[i-depth]['high'] == window['high'].max():
                pivots.append((candidate_idx, 'peak', dataframe.iloc[i-depth]['high']))

        # Remove duplicates (sequential points of the same type or at same index)
        # and ensure alternating peaks and valleys for the pattern
        clean_pivots = []
        for p in pivots:
            if not clean_pivots:
                clean_pivots.append(p)
                continue

            # If same index, skip
            if p[0] == clean_pivots[-1][0]:
                continue

            # If same type, keep the more extreme one
            if p[1] == clean_pivots[-1][1]:
                if p[1] == 'valley':
                    if p[2] < clean_pivots[-1][2]:
                        clean_pivots[-1] = p
                else:
                    if p[2] > clean_pivots[-1][2]:
                        clean_pivots[-1] = p
            else:
                clean_pivots.append(p)

        return clean_pivots

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # We don't populate indicators here for Wolfe Waves as it depends on
        # sequence of pivots which is best handled in signals.
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['enter_long'] = 0

        # Find all pivots confirmed up to the current state
        # In backtesting, we need to iterate to simulate real-time discovery
        # This is computationally intensive but avoids lookahead.

        pivots = self.find_pivots(dataframe, depth=12)

        if len(pivots) < 5:
            return dataframe

        for i in range(4, len(pivots)):
            last_5 = pivots[i-4:i+1]

            # Bullish Wolfe Wave: Valley(1), Peak(2), Valley(3), Peak(4), Valley(5)
            if last_5[0][1] == 'valley' and last_5[1][1] == 'peak' and \
               last_5[2][1] == 'valley' and last_5[3][1] == 'peak' and \
               last_5[4][1] == 'valley':

                idx1, _, p1 = last_5[0]
                idx2, _, p2 = last_5[1]
                idx3, _, p3 = last_5[2]
                idx4, _, p4 = last_5[3]
                idx5, _, p5 = last_5[4]

                # Wolfe Wave Conditions (Bullish)
                if p3 < p1 and p4 < p2 and p4 > p1 and p5 < p3:
                    # Confirmation index: When point 5 was confirmed
                    # Since find_pivots uses depth, confirmation happens at idx5 + depth
                    confirm_idx = idx5 + 12
                    if confirm_idx < len(dataframe):
                        dataframe.loc[confirm_idx, 'enter_long'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['exit_long'] = 0
        return dataframe
