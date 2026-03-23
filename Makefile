.PHONY: all install fetch-data backtest backtest-wolfe plot plot-wolfe heatmap diff-heatmap prob-delta-heatmap

all: install fetch-data backtest backtest-wolfe plot plot-wolfe heatmap diff-heatmap prob-delta-heatmap

install:
	@echo "Creating virtual environment and installing dependencies..."
	python3 -m venv .venv
	@. .venv/bin/activate && pip install uv
	@. .venv/bin/activate && uv pip install freqtrade plotly scipy

fetch-data:
	@echo "Fetching data..."
	@. .venv/bin/activate && freqtrade download-data --exchange kucoin --pairs BTC/USDT --days 100 -t 1h 4h 1d 1w --userdir user_data

backtest:
	@echo "Running backtest..."
	@. .venv/bin/activate && freqtrade backtesting --strategy profitable_strategy --userdir user_data --export trades

backtest-wolfe:
	@echo "Running Wolfe Waves backtest..."
	@. .venv/bin/activate && freqtrade backtesting --strategy WolfeWavesStrategy --userdir user_data --export trades

plot:
	@echo "Plotting..."
	@. .venv/bin/activate && freqtrade plot-dataframe --strategy profitable_strategy --userdir user_data -p BTC/USDT

plot-wolfe:
	@echo "Plotting Wolfe Waves..."
	@. .venv/bin/activate && freqtrade plot-dataframe --strategy WolfeWavesStrategy --userdir user_data -p BTC/USDT

heatmap:
	@echo "Generating Probability Heatmap..."
	@. .venv/bin/activate && python3 user_data/scripts/plot_heatmap.py

diff-heatmap:
	@echo "Generating Price Change Probability Heatmap..."
	@. .venv/bin/activate && python3 user_data/scripts/plot_diff_heatmap.py

prob-delta-heatmap:
	@echo "Generating Probability Delta Heatmap..."
	@. .venv/bin/activate && python3 user_data/scripts/plot_prob_delta_heatmap.py
