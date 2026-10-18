
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler
from data import load_prices, fetch_prices, refresh_prices
from indicators import calculate_indicators, get_market_regime
import pandas as pd
from screener import screen_stocks
from backtest import run_backtest
from fastapi import Path as ApiPath
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

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

logger = logging.getLogger(__name__)

IST = ZoneInfo("Asia/Kolkata")

scheduler = BackgroundScheduler(timezone=IST)


def scheduled_price_refresh():
    """Refresh daily prices and log the outcome."""
    try:
        prices = refresh_prices(period="10d")

        latest_date = prices["date"].max()

        logger.info(
            "Scheduled refresh completed. Rows=%s, symbols=%s, latest_date=%s",
            len(prices),
            prices["symbol"].nunique(),
            latest_date,
        )

    except Exception:
        logger.exception("Scheduled price refresh failed")


@app.on_event("startup")
def start_scheduler():
    if not scheduler.running:
        # Primary refresh after the market session.
        scheduler.add_job(
            scheduled_price_refresh,
            trigger="cron",
            day_of_week="mon-fri",
            hour=16,
            minute=30,
            id="daily_price_refresh",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )

        # Retry later in case daily data was not yet available.
        scheduler.add_job(
            scheduled_price_refresh,
            trigger="cron",
            day_of_week="mon-fri",
            hour=18,
            minute=0,
            id="daily_price_refresh_retry",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )

        scheduler.start()
        logger.info("Daily price refresh scheduler started")


@app.on_event("shutdown")
def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)


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


@app.get("/api/backtest")
def backtest(
    min_return_20d: float | None = Query(default=None),
    min_zscore: float | None = Query(default=None),
    min_volume_ratio: float | None = Query(default=None),
):
    prices = get_data()

    try:
        return run_backtest(
            prices,
            min_return_20d=min_return_20d,
            min_zscore=min_zscore,
            min_volume_ratio=min_volume_ratio,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

@app.post("/api/refresh")
def refresh_data():
    try:
        prices = refresh_prices(period="10d")

        latest_date = prices["date"].max()

        return {
            "message": "Price data refreshed successfully.",
            "rows": len(prices),
            "symbols": int(prices["symbol"].nunique()),
            "latest_date": str(latest_date)[:10],
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Price refresh failed: {str(exc)}",
        ) from exc


@app.get("/api/data-status")
def data_status():
    try:
        prices = load_prices()

        if prices.empty:
            raise HTTPException(
                status_code=503,
                detail="Price dataset is empty.",
            )

        latest_date = prices["date"].max()

        # This is the file's modification time, not the market date.
        from data import DATA_FILE

        last_refresh = datetime.fromtimestamp(
            DATA_FILE.stat().st_mtime,
            tz=IST,
        )

        return {
            "latest_market_date": str(latest_date)[:10],
            "last_refresh_at": last_refresh.isoformat(),
            "symbols": int(prices["symbol"].nunique()),
            "rows": int(len(prices)),
        }

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Could not read data status: {exc}",
        ) from exc