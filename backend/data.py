from pathlib import Path

import pandas as pd
import yfinance as yf

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DATA_FILE = DATA_DIR / "prices.csv"

BENCHMARK = "^NSEI"

# Candidate NIFTY 50 constituents; verify against the official index list.
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

COLUMNS = ["date", "symbol", "close", "volume"]


def _download_symbol(ticker: str, symbol: str, period: str) -> pd.DataFrame:
    """Download daily adjusted prices for one ticker."""
    history = yf.Ticker(ticker).history(
        period=period,
        interval="1d",
        auto_adjust=True,
    )

    if history.empty or "Close" not in history.columns:
        raise ValueError(f"No price data returned for {ticker}")

    frame = history[["Close", "Volume"]].copy()
    frame = frame.rename(
        columns={
            "Close": "close",
            "Volume": "volume",
        }
    )

    # Convert Yahoo Finance's possibly timezone-aware index to dates.
    frame["date"] = pd.to_datetime(history.index).date
    frame["symbol"] = symbol

    frame = frame.reset_index(drop=True)
    frame = frame[COLUMNS]

    frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
    frame["volume"] = pd.to_numeric(frame["volume"], errors="coerce")

    frame = frame.dropna(subset=["date", "symbol", "close"])
    frame = frame[frame["close"] > 0]

    if frame.empty:
        raise ValueError(f"No valid prices returned for {ticker}")

    return frame


def load_prices() -> pd.DataFrame:
    """Load the locally stored price dataset."""
    if not DATA_FILE.exists():
        raise FileNotFoundError(
            f"No price data found at {DATA_FILE}. "
            "Run fetch_prices() first."
        )

    prices = pd.read_csv(DATA_FILE, parse_dates=["date"])

    missing = set(COLUMNS) - set(prices.columns)
    if missing:
        raise ValueError(
            f"Price dataset is missing columns: {sorted(missing)}"
        )

    prices["symbol"] = prices["symbol"].astype(str)
    prices["close"] = pd.to_numeric(prices["close"], errors="coerce")
    prices["volume"] = pd.to_numeric(prices["volume"], errors="coerce")

    prices = prices.dropna(subset=["date", "symbol", "close"])
    prices = prices[prices["close"] > 0]
    prices = prices.drop_duplicates(
        subset=["date", "symbol"],
        keep="last",
    )
    prices = prices.sort_values(["symbol", "date"]).reset_index(drop=True)

    return prices[COLUMNS]


def _save_prices_safely(prices: pd.DataFrame) -> None:
    """Write a complete dataset to a temporary file before replacing the CSV."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    prices = prices[COLUMNS].copy()
    prices = prices.dropna(subset=["date", "symbol", "close"])
    prices = prices.drop_duplicates(
        subset=["date", "symbol"],
        keep="last",
    )
    prices = prices.sort_values(["symbol", "date"])

    temp_file = DATA_FILE.with_suffix(".tmp")

    try:
        prices.to_csv(temp_file, index=False)
        temp_file.replace(DATA_FILE)
    finally:
        if temp_file.exists():
            temp_file.unlink()


def _update_prices(period: str) -> pd.DataFrame:
    """
    Download recent or full price history and merge it with existing data.

    Existing history is preserved for symbols whose downloads fail.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if DATA_FILE.exists():
        existing = load_prices()
    else:
        existing = pd.DataFrame(columns=COLUMNS)

    tickers = [(BENCHMARK, "NIFTY50")]
    tickers.extend((f"{symbol}.NS", symbol) for symbol in SYMBOLS)

    downloaded = []
    failed = []
    successful_symbols = set()

    for ticker, symbol in tickers:
        try:
            frame = _download_symbol(ticker, symbol, period)

            downloaded.append(frame)
            successful_symbols.add(symbol)

            print(f"Downloaded {symbol}: {len(frame)} rows")

        except Exception as exc:
            failed.append({"symbol": symbol, "error": str(exc)})
            print(f"Failed {ticker}: {exc}")

    if not downloaded:
        raise RuntimeError(
            "No price data was downloaded. "
            "The existing CSV has not been replaced."
        )

    fresh = pd.concat(downloaded, ignore_index=True)

    # Merge instead of replacing the whole file.
    # New rows replace older values for the same symbol and date.
    combined = pd.concat([existing, fresh], ignore_index=True)

    combined["date"] = pd.to_datetime(combined["date"])
    combined["symbol"] = combined["symbol"].astype(str)
    combined["close"] = pd.to_numeric(combined["close"], errors="coerce")
    combined["volume"] = pd.to_numeric(combined["volume"], errors="coerce")

    combined = combined.dropna(subset=["date", "symbol", "close"])
    combined = combined[combined["close"] > 0]
    combined = combined.drop_duplicates(
        subset=["date", "symbol"],
        keep="last",
    )
    combined = combined.sort_values(["symbol", "date"]).reset_index(drop=True)

    # Refuse to save a dataset that has lost all benchmark history.
    if combined[combined["symbol"] == "NIFTY50"].empty:
        raise RuntimeError(
            "NIFTY50 benchmark history is missing. "
            "The existing CSV has not been replaced."
        )

    _save_prices_safely(combined)

    print(f"\nSaved {len(combined):,} rows to {DATA_FILE}")
    print(f"Successfully refreshed: {len(successful_symbols)} symbols")
    print(f"Failed downloads: {len(failed)}")

    if failed:
        print("Some symbols could not be refreshed:")
        for item in failed:
            print(f"  {item['symbol']}: {item['error']}")

    return combined


def fetch_prices(period: str = "2y") -> pd.DataFrame:
    """
    Download historical daily prices.

    Use for initial data setup or an intentional historical refresh.
    Existing history is merged rather than discarded.
    """
    return _update_prices(period=period)


def refresh_prices(period: str = "10d") -> pd.DataFrame:
    """
    Refresh recent daily prices while preserving existing history.

    Ten calendar days provides a buffer for weekends, holidays,
    and delayed availability of the latest trading session.
    """
    return _update_prices(period=period)


if __name__ == "__main__":
    refresh_prices()