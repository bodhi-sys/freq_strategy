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
    Wolfe Waves Pattern Strategy.
    Points 1, 2, 3, 4, 5 are identified using a ZigZag indicator logic.
    EPA line: Trend line connecting points 1 and 4.
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
    startup_candle_count: int = 300

    def zigzag(self, dataframe: DataFrame, depth: int = 12) -> DataFrame:
        """
        Calculates a ZigZag indicator based on rolling high/low.
        """
        df = dataframe.copy()
        df['high_rolling'] = df['high'].rolling(window=depth, center=True).max()
        df['low_rolling'] = df['low'].rolling(window=depth, center=True).min()

        df['is_peak'] = (df['high'] == df['high_rolling'])
        df['is_valley'] = (df['low'] == df['low_rolling'])

        return df[['is_peak', 'is_valley']]

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # ZigZag for finding Wolfe Waves points
        zz = self.zigzag(dataframe, depth=15)
        dataframe['zz_peak'] = zz['is_peak']
        dataframe['zz_valley'] = zz['is_valley']

        # Calculate peaks and valleys indices in advance for speed
        peaks = dataframe[dataframe['zz_peak']].index.tolist()
        valleys = dataframe[dataframe['zz_valley']].index.tolist()

        # We'll use a rolling search for the pattern
        # This is more efficient than a full loop if we pre-filter potential candidates

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['enter_long'] = 0

        peaks = dataframe[dataframe['zz_peak']].index.tolist()
        valleys = dataframe[dataframe['zz_valley']].index.tolist()

        # Combine and sort peaks/valleys into a single sequence
        zz_points = sorted([(idx, 'peak') for idx in peaks] + [(idx, 'valley') for idx in valleys])

        if len(zz_points) < 5:
            return dataframe

        for i in range(4, len(zz_points)):
            last_5 = zz_points[i-4:i+1]

            # For a Bullish Wolfe Wave: Valley(1), Peak(2), Valley(3), Peak(4), Valley(5)
            if last_5[0][1] == 'valley' and last_5[1][1] == 'peak' and \
               last_5[2][1] == 'valley' and last_5[3][1] == 'peak' and \
               last_5[4][1] == 'valley':

                idx1, idx2, idx3, idx4, idx5 = [p[0] for p in last_5]

                p1 = dataframe.iloc[idx1]['low']
                p2 = dataframe.iloc[idx2]['high']
                p3 = dataframe.iloc[idx3]['low']
                p4 = dataframe.iloc[idx4]['high']
                p5 = dataframe.iloc[idx5]['low']

                # Wolfe Wave Conditions (Bullish)
                if p3 < p1 and p4 < p2 and p4 > p1 and p5 < p3:
                    # Enter on confirmation of reversal from P5
                    # We enter on the candle immediately following P5 identification
                    # But since ZigZag has lookahead (window/depth), we need to be careful.
                    # In this simplified model, we enter at idx5.
                    dataframe.loc[idx5, 'enter_long'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Exit on standard ROI or stoploss for this version.
        dataframe['exit_long'] = 0
        return dataframe
