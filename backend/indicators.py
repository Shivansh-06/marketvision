
import pandas as pd


def calculate_indicators(prices: pd.DataFrame) -> pd.DataFrame:
    """Calculate statistical indicators for the latest observation of each stock."""

    if prices.empty:
        return pd.DataFrame(
            columns=[
                "symbol",
                "date",
                "close",
                "return_20d",
                "return_zscore",
                "volume_ratio",
            ]
        )

    outputs = []

    for symbol, group in prices.groupby("symbol", sort=False):
        group = group.sort_values("date").copy()

        # Daily percentage returns
        group["daily_return"] = group["close"].pct_change()

        # Return over the previous 20 trading intervals
        group["return_20d"] = group["close"].pct_change(20)

        # Compare today's return with the preceding 20 daily returns.
        # Shift ensures today's return is excluded from its reference window.
        historical_returns = group["daily_return"].shift(1)

        rolling_mean = historical_returns.rolling(
            window=20, min_periods=10
        ).mean()

        rolling_std = historical_returns.rolling(
            window=20, min_periods=10
        ).std(ddof=1)

        group["return_zscore"] = (
            (group["daily_return"] - rolling_mean)
            / rolling_std.replace(0, float("nan"))
        )

        # Compare today's volume with the previous 20 sessions.
        historical_volume = group["volume"].shift(1)

        volume_mean = historical_volume.rolling(
            window=20, min_periods=10
        ).mean()

        group["volume_ratio"] = (
            group["volume"]
            / volume_mean.replace(0, float("nan"))
        )

        outputs.append(group)

    combined = pd.concat(outputs, ignore_index=True)

    # Keep the most recent observation for each symbol.
    latest = (
        combined.sort_values("date")
        .groupby("symbol", sort=False)
        .tail(1)
        .copy()
    )

    columns = [
        "symbol",
        "date",
        "close",
        "return_20d",
        "return_zscore",
        "volume_ratio",
    ]

    return latest[columns].sort_values("symbol").reset_index(drop=True)


def get_market_regime(prices: pd.DataFrame) -> dict:
    """Classify NIFTY 50 using 50-day and 200-day moving averages."""

    index_data = prices[
        prices["symbol"].str.upper() == "NIFTY50"
    ].sort_values("date").copy()

    if len(index_data) < 200:
        return {
            "symbol": "NIFTY50",
            "regime": "insufficient_data",
            "message": "At least 200 observations are required.",
        }

    close = index_data["close"]

    sma50 = close.rolling(window=50).mean().iloc[-1]
    sma200 = close.rolling(window=200).mean().iloc[-1]

    daily_returns = close.pct_change()

    volatility_20d = (
        daily_returns.rolling(window=20).std().iloc[-1]
        * (252 ** 0.5)
    )

    current_close = close.iloc[-1]

    if current_close > sma200 and sma50 > sma200:
        regime = "bullish"

    elif current_close < sma200 and sma50 < sma200:
        regime = "bearish"

    else:
        regime = "sideways_or_transition"

    return {
        "symbol": "NIFTY50",
        "as_of": index_data["date"].iloc[-1].date().isoformat(),
        "regime": regime,
        "close": round(float(current_close), 2),
        "sma50": round(float(sma50), 2),
        "sma200": round(float(sma200), 2),
        "realized_volatility_20d_annualized": round(
            float(volatility_20d), 4
        ),
    }
