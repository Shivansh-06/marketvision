
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from data import load_prices, fetch_prices
from indicators import calculate_indicators, get_market_regime
import pandas as pd
from screener import screen_stocks
from fastapi import Path as ApiPath

app = FastAPI(
    title="Statistical Stock Screener",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_data():
    prices = load_prices()

    if prices.empty:
        raise HTTPException(
            status_code=503,
            detail="No market data available. Check data/prices.csv.",
        )

    return prices


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/regime")
def regime():
    prices = get_data()
    return get_market_regime(prices)


@app.get("/api/screener")
def screener(
    min_return_20d: float | None = Query(default=None),
    min_zscore: float | None = Query(default=None),
    min_volume_ratio: float | None = Query(default=None),
):
    prices = get_data()
    metrics = calculate_indicators(prices)

    results = screen_stocks(
        metrics,
        min_return_20d=min_return_20d,
        min_zscore=min_zscore,
        min_volume_ratio=min_volume_ratio,
    )

    return {
        "count": len(results),
        "results": results.to_dict(orient="records"),
    }

@app.post("/api/refresh")
def refresh_data():
    try:
        prices = fetch_prices()
        return {
            "status": "success",
            "rows": len(prices),
            "symbols": int(prices["symbol"].nunique()),
        }
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Price refresh failed: {exc}",
        ) from exc

@app.get("/api/stock/{symbol}/history")
def stock_history(symbol: str, days: int = 126):
    prices = get_data()

    symbol = symbol.upper()

    available_symbols = set(prices["symbol"].unique())
    if symbol not in available_symbols or symbol == "NIFTY50":
        raise HTTPException(status_code=404, detail="Stock not found.")

    stock = prices[prices["symbol"] == symbol].sort_values("date").tail(days)

    benchmark = (
        prices[prices["symbol"] == "NIFTY50"]
        .sort_values("date")[["date", "close"]]
        .rename(columns={"close": "nifty_close"})
    )

    history = stock.merge(benchmark, on="date", how="left")

    return {
        "symbol": symbol,
        "count": len(history),
        "history": history.where(pd.notna(history), None).to_dict(orient="records"),
    }