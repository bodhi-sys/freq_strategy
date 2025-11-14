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


class macd_bollinger_strategy(IStrategy):
    """
    This strategy uses MACD and Bollinger Bands on two different timeframes.
    """
    INTERFACE_VERSION = 3

    # Timeframes
    timeframe = '1h'
    informative_timeframe = '2h'

    # Can this strategy go short?
    can_short: bool = False

    # Minimal ROI designed for the strategy.
    minimal_roi = {
        "0": 0.04
    }

    # Optimal stoploss designed for the strategy.
    stoploss = -0.10

    # Run "populate_indicators()" only for new candle.
    process_only_new_candles = True

    # These values can be overridden in the config.
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    # Number of candles the strategy requires before producing valid signals
    startup_candle_count: int = 30

    # Optional order type mapping.
    order_types = {
        "entry": "limit",
        "exit": "limit",
        "stoploss": "market",
        "stoploss_on_exchange": False
    }

    # Optional order time in force.
    order_time_in_force = {
        "entry": "GTC",
        "exit": "GTC"
    }

    @property
    def plot_config(self):
        return {
            "main_plot": {
                'bb_middleband': {'color': 'cyan'},
                'bb_lowerband': {'color': 'blue'},
                'bb_upperband': {'color': 'blue'},
            },
            "subplots": {
                "MACD": {
                    "macd": {"color": "blue"},
                    "macdsignal": {"color": "orange"},
                    'bb_lowerband_macd': {'color': 'red'},
                },
            }
        }
    @informative('2h')
    def populate_indicators_2h(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Bollinger Bands for the informative timeframe
        bollinger_2h = qtpylib.bollinger_bands(qtpylib.typical_price(dataframe), window=20, stds=2)
        dataframe['bb_lowerband_2h'] = bollinger_2h['lower']

        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # MACD
        macd = ta.MACD(dataframe)
        dataframe['macd'] = macd['macd']
        dataframe['macdsignal'] = macd['macdsignal']

        # Bollinger Bands on price for the main timeframe
        bollinger = qtpylib.bollinger_bands(qtpylib.typical_price(dataframe), window=20, stds=2)
        dataframe['bb_lowerband'] = bollinger['lower']
        dataframe['bb_middleband'] = bollinger['mid']
        dataframe['bb_upperband'] = bollinger['upper']

        # Bollinger Bands on MACD signal for the main timeframe
        bollinger_macd = qtpylib.bollinger_bands(dataframe['macdsignal'], window=20, stds=2)
        dataframe['bb_lowerband_macd'] = bollinger_macd['lower']

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Based on TA indicators, populates the entry signal for the given dataframe
        :param dataframe: DataFrame
        :param metadata: Additional information, like the currently traded pair
        :return: DataFrame with entry columns populated
        """
        dataframe.loc[
            (
                (qtpylib.crossed_above(dataframe['macdsignal'], dataframe['bb_lowerband_macd'])) &
                (dataframe['bb_lowerband'] > 0) &
                (dataframe['bb_lowerband_2h'] > 0) &
                (dataframe['volume'] > 0)
            ),
            'enter_long'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Based on TA indicators, populates the exit signal for the given dataframe
        :param dataframe: DataFrame
        :param metadata: Additional information, like the currently traded pair
        :return: DataFrame with exit columns populated
        """
        dataframe.loc[
            (
                (qtpylib.crossed_above(dataframe['close'], dataframe['bb_middleband'])) &
                (dataframe['volume'] > 0)
            ),
            'exit_long'] = 1
        return dataframe
