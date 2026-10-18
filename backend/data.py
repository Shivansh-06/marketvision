
from pathlib import Path

import pandas as pd
import yfinance as yf

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DATA_FILE = DATA_DIR / "prices.csv"

BENCHMARK = "^NSEI"

# NIFTY 50 constituents; Yahoo Finance ticker symbols
SYMBOLS = [
    "ADANIENT", "ADANIPORTS", "APOLLOHOSP", "ASIANPAINT", "AXISBANK",
    "BAJAJ-AUTO", "BAJAJFINSV", "BAJFINANCE", "BEL", "BHARTIARTL",
    "CIPLA", "COALINDIA", "DRREDDY", "EICHERMOT", "ETERNAL",
    "GRASIM", "HCLTECH", "HDFCBANK", "HDFCLIFE", "HINDALCO",
    "HINDUNILVR", "ICICIBANK", "INDIGO", "INFY", "ITC",
    "JIOFIN", "JSWSTEEL", "KOTAKBANK", "LT", "M&M",
    "MARUTI", "MAXHEALTH", "NESTLEIND", "NTPC", "ONGC",
    "POWERGRID", "RELIANCE", "SBILIFE", "SBIN", "SHRIRAMFIN",
    "SUNPHARMA", "TATACONSUM", "TATASTEEL", "TCS", "TECHM",
    "TITAN", "TMPV", "TRENT", "ULTRACEMCO",
]


def fetch_prices(period: str = "2y") -> pd.DataFrame:
    """Download daily adjusted prices for the index and its constituents."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    downloaded = []
    failed = []

    tickers = [(BENCHMARK, "NIFTY50")]
    tickers.extend((f"{symbol}.NS", symbol) for symbol in SYMBOLS)

    for ticker, symbol in tickers:
        try:
            history = yf.Ticker(ticker).history(
                period=period,
                interval="1d",
                auto_adjust=True,
            )

            if history.empty or "Close" not in history.columns:
                failed.append(ticker)
                print(f"Skipped {ticker}: no price data")
                continue

            frame = history[["Close", "Volume"]].copy()
            frame = frame.rename(
                columns={"Close": "close", "Volume": "volume"}
            )
            frame["symbol"] = symbol
            frame["date"] = pd.to_datetime(frame.index).date
            frame = frame.reset_index(drop=True)
            frame = frame[["date", "symbol", "close", "volume"]]
            downloaded.append(frame)

            print(f"Downloaded {symbol}: {len(frame)} rows")

        except Exception as exc:
            failed.append(ticker)
            print(f"Failed {ticker}: {exc}")

    if not downloaded:
        raise RuntimeError(
            "No price data was downloaded. Existing CSV was not replaced."
        )

    prices = pd.concat(downloaded, ignore_index=True)
    prices = prices.dropna(subset=["close"])
    prices = prices.sort_values(["symbol", "date"])

    # Replace the CSV only after at least some downloads succeeded.
    prices.to_csv(DATA_FILE, index=False)

    print(f"\nSaved {len(prices):,} rows to {DATA_FILE}")
    print(f"Successful symbols: {prices['symbol'].nunique()}")
    print(f"Failed tickers: {failed}")

    return prices


def load_prices() -> pd.DataFrame:
    if not DATA_FILE.exists():
        raise FileNotFoundError(
            f"No price data found at {DATA_FILE}. Run fetch_prices() first."
        )

    prices = pd.read_csv(DATA_FILE, parse_dates=["date"])
    prices["symbol"] = prices["symbol"].astype(str)
    return prices


if __name__ == "__main__":
    fetch_prices()
