
import pandas as pd


def screen_stocks(
    metrics: pd.DataFrame,
    min_return_20d: float | None = None,
    min_zscore: float | None = None,
    min_volume_ratio: float | None = None,
    regime: str | None = None,
) -> pd.DataFrame:
    """
    Filter stocks using their latest calculated indicators.

    Parameters
    ----------
    metrics:
        Output from calculate_indicators().

    min_return_20d:
        Minimum 20-day return as a decimal.
        Example: 0.05 means 5%.

    min_zscore:
        Minimum daily return Z-score.
        Example: 2 means two standard deviations above
        the historical mean.

    min_volume_ratio:
        Minimum volume relative to the previous 20-session
        average. Example: 2 means twice the average volume.

    regime:
        Optional market regime filter. Supported values:
        bullish, bearish, sideways_or_transition.
        This filter is applied by the API, not inferred
        from individual stock metrics.
    """

    if metrics.empty:
        return metrics.copy()

    result = metrics.copy()
    result = result[result["symbol"] != "NIFTY50"]

    if min_return_20d is not None:
        result = result[
            result["return_20d"] >= min_return_20d
        ]

    if min_zscore is not None:
        result = result[
            result["return_zscore"] >= min_zscore
        ]

    if min_volume_ratio is not None:
        result = result[
            result["volume_ratio"] >= min_volume_ratio
        ]

    # Sort strongest 20-day returns first.
    result = result.sort_values(
        "return_20d",
        ascending=False,
        na_position="last",
    )

    return result.reset_index(drop=True)
