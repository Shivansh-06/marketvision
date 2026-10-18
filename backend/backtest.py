
import pandas as pd


def _calculate_metrics(returns: pd.Series) -> dict:
    returns = returns.dropna()

    if returns.empty:
        return {
            "sample_size": 0,
            "mean_return": None,
            "median_return": None,
            "win_rate": None,
        }

    return {
        "sample_size": int(len(returns)),
        "mean_return": float(returns.mean()),
        "median_return": float(returns.median()),
        "win_rate": float((returns > 0).mean()),
    }


def run_backtest(
    prices: pd.DataFrame,
    min_return_20d: float | None = None,
    min_zscore: float | None = None,
    min_volume_ratio: float | None = None,
    horizons: tuple[int, ...] = (1, 5),
) -> dict:
    """
    Historical signal study.

    Signals use information available at each day's close.
    Forward returns are outcomes, not inputs to the signal.
    This is not yet an executable trading simulation.
    """
    if prices.empty:
        raise ValueError("Price dataset is empty.")

    required = {"date", "symbol", "close", "volume"}
    missing = required - set(prices.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    if not horizons or any(h <= 0 for h in horizons):
        raise ValueError("Horizons must contain positive integers.")

    data = prices.copy()
    data["date"] = pd.to_datetime(data["date"]).dt.normalize()
    data["close"] = pd.to_numeric(data["close"], errors="coerce")
    data["volume"] = pd.to_numeric(data["volume"], errors="coerce")
    data = data.dropna(subset=["date", "symbol", "close"])
    data = data.sort_values(["symbol", "date"])
    data = data.drop_duplicates(["symbol", "date"], keep="last")

    # Calculate benchmark forward returns on the benchmark's own timeline.
    benchmark = (
        data.loc[data["symbol"] == "NIFTY50", ["date", "close"]]
        .sort_values("date")
        .drop_duplicates("date")
        .copy()
    )

    if benchmark.empty:
        raise ValueError("NIFTY50 benchmark data is missing.")

    for horizon in horizons:
        benchmark[f"benchmark_return_{horizon}d"] = (
            benchmark["close"].shift(-horizon) / benchmark["close"] - 1
        )

    benchmark_columns = [
        "date",
        *[f"benchmark_return_{h}d" for h in horizons],
    ]

    benchmark = benchmark[benchmark_columns]

    stock_frames = []

    for symbol, group in data.groupby("symbol", sort=False):
        if symbol == "NIFTY50":
            continue

        group = group.sort_values("date").copy()
        group["daily_return"] = group["close"].pct_change()
        group["return_20d"] = group["close"].pct_change(20)

        # Exclude the current day's return from its reference distribution.
        previous_returns = group["daily_return"].shift(1)
        rolling_mean = previous_returns.rolling(
            20, min_periods=10
        ).mean()
        rolling_std = previous_returns.rolling(
            20, min_periods=10
        ).std()

        group["return_zscore"] = (
            group["daily_return"] - rolling_mean
        ) / rolling_std.replace(0, float("nan"))

        previous_volume_mean = (
            group["volume"].shift(1).rolling(20, min_periods=10).mean()
        )
        group["volume_ratio"] = (
            group["volume"] / previous_volume_mean.replace(0, float("nan"))
        )

        for horizon in horizons:
            group[f"forward_return_{horizon}d"] = (
                group["close"].shift(-horizon) / group["close"] - 1
            )

        stock_frames.append(group)

    if not stock_frames:
        raise ValueError("No individual stock price data found.")

    history = pd.concat(stock_frames, ignore_index=True)
    history = history.merge(benchmark, on="date", how="left")

    for horizon in horizons:
        history[f"excess_return_{horizon}d"] = (
            history[f"forward_return_{horizon}d"]
            - history[f"benchmark_return_{horizon}d"]
        )

    # Define the signal using only historical/current-close indicators.
    mask = history["return_20d"].notna()

    if min_return_20d is not None:
        mask &= history["return_20d"] >= min_return_20d

    if min_zscore is not None:
        mask &= history["return_zscore"] >= min_zscore

    if min_volume_ratio is not None:
        mask &= history["volume_ratio"] >= min_volume_ratio

    signals = history.loc[mask].copy()
    results = {}

    for horizon in horizons:
        stock_col = f"forward_return_{horizon}d"
        benchmark_col = f"benchmark_return_{horizon}d"
        excess_col = f"excess_return_{horizon}d"

        # Keep only rows with all three comparable outcomes.
        valid = signals[
            [stock_col, benchmark_col, excess_col]
        ].dropna()

        results[f"{horizon}d"] = {
            "stock": _calculate_metrics(valid[stock_col]),
            "benchmark": _calculate_metrics(valid[benchmark_col]),
            "excess_return": _calculate_metrics(valid[excess_col]),
        }

    return {
        "signal_count": int(len(signals)),
        "date_start": str(history["date"].min().date()),
        "date_end": str(history["date"].max().date()),
        "thresholds": {
            "min_return_20d": min_return_20d,
            "min_zscore": min_zscore,
            "min_volume_ratio": min_volume_ratio,
        },
        "results": results,
        "methodology": (
            "Signals use information available at each day's close. "
            "Forward returns are close-to-close outcomes over the next "
            "N observations for each stock. Benchmark returns use the "
            "NIFTY50 series directly and are matched by signal date. "
            "This is a historical signal study, not a trading simulation."
        ),
    }
