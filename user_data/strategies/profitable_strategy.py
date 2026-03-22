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


class profitable_strategy(IStrategy):
    """
    This is a strategy that uses EMA crossovers and RSI.
    """
    INTERFACE_VERSION = 3

    # Timeframe
    timeframe = '1h'

    # Can this strategy go short?
    can_short: bool = False

    # Minimal ROI designed for the strategy.
    minimal_roi = {
        "0": 0.05
    }

    # Optimal stoploss designed for the strategy.
    stoploss = -0.05

    # Run "populate_indicators()" only for new candle.
    process_only_new_candles = True

    # Number of candles the strategy requires before producing valid signals
    startup_candle_count: int = 200

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # RSI
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)

        # EMA
        dataframe['ema20'] = ta.EMA(dataframe, timeperiod=20)
        dataframe['ema50'] = ta.EMA(dataframe, timeperiod=50)
        dataframe['ema200'] = ta.EMA(dataframe, timeperiod=200)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                (qtpylib.crossed_above(dataframe['ema20'], dataframe['ema50'])) &
                (dataframe['close'] > dataframe['ema200']) &
                (dataframe['rsi'] > 50) &
                (dataframe['rsi'] < 70) &
                (dataframe['volume'] > 0)
            ),
            'enter_long'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                (qtpylib.crossed_below(dataframe['ema20'], dataframe['ema50']))
            ) &
            (dataframe['volume'] > 0),
            'exit_long'] = 1
        return dataframe
