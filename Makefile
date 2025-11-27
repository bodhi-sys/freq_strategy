.PHONY: all install fetch-data backtest plot

all: install fetch-data backtest plot

install:
	@echo "Creating virtual environment and installing dependencies..."
	python3 -m venv .venv
	@. .venv/bin/activate && pip install uv
	@. .venv/bin/activate && uv pip install freqtrade plotly

fetch-data:
	@echo "Fetching data..."
	@. .venv/bin/activate && freqtrade download-data --exchange kucoin --pairs BTC/USDT --days 10 -t 1h --userdir user_data
	@. .venv/bin/activate && freqtrade download-data --exchange kucoin --pairs BTC/USDT --days 10 -t 2h --userdir user_data

backtest:
	@echo "Running backtest..."
	@. .venv/bin/activate && freqtrade backtesting --strategy macd_bollinger_strategy --userdir user_data

plot:
	@echo "Plotting..."
	@. .venv/bin/activate && freqtrade plot-dataframe --strategy macd_bollinger_strategy --userdir user_data -p BTC/USDT
