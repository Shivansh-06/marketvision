
from pathlib import Path

import pandas as pd
import yfinance as yf

DATA_FILE = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "prices.csv"
)

SYMBOLS = [
    "^NSEI",
    "RELIANCE.NS",
    "TCS.NS",
    "INFY.NS",
    "HDFCBANK.NS",
]


def fetch_prices(
    period: str = "2y",
) -> pd.DataFrame:
    """Fetch daily adjusted-price history for the initial universe."""

    frames = []

    for ticker in SYMBOLS:
        print(f"Fetching {ticker}...")

        try:
            history = yf.Ticker(ticker).history(
                period=period,
                interval="1d",
                auto_adjust=True,
            )

            if history.empty:
                print(f"No data returned for {ticker}")
                continue

            frame = history.reset_index()

            # Yahoo Finance can return different date column names.
            date_column = (
                "Date" if "Date" in frame.columns else "Datetime"
            )

            frame = frame.rename(
                columns={
                    date_column: "date",
                    "Close": "close",
                    "Volume": "volume",
                }
            )

            frame["date"] = pd.to_datetime(
                frame["date"], utc=True
            ).dt.tz_localize(None).dt.normalize()

            frame["symbol"] = (
                "NIFTY50" if ticker == "^NSEI"
                else ticker.removesuffix(".NS")
            )

            frame = frame[
                ["date", "symbol", "close", "volume"]
            ]

            frames.append(frame)

        except Exception as exc:
            print(f"Failed to fetch {ticker}: {exc}")

    if not frames:
        raise RuntimeError(
            "No market data was downloaded. Check connectivity "
            "and the data provider."
        )

    prices = pd.concat(frames, ignore_index=True)

    prices = prices.dropna(
        subset=["date", "symbol", "close", "volume"]
    )

    prices = prices[prices["close"] > 0]

    prices = prices.drop_duplicates(
        subset=["date", "symbol"]
    )

    return prices.sort_values(
        ["symbol", "date"]
    ).reset_index(drop=True)


def load_prices() -> pd.DataFrame:
    """Load previously downloaded data from CSV."""

    if not DATA_FILE.exists():
        return pd.DataFrame(
            columns=["date", "symbol", "close", "volume"]
        )

    return pd.read_csv(
        DATA_FILE,
        parse_dates=["date"],
    )


if __name__ == "__main__":
    DATA_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    prices = fetch_prices(period="2y")
    prices.to_csv(DATA_FILE, index=False)

    print(f"\nSaved {len(prices):,} rows to {DATA_FILE}")
    print("\nRows per symbol:")
    print(prices.groupby("symbol").size())
    print("\nLatest observations:")
    print(prices.groupby("symbol").tail(1).to_string(index=False))
