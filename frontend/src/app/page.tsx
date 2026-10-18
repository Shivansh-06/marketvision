"use client";

import { useEffect, useRef, useState } from "react";
import {
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  Bar,
} from "recharts";

const API = "http://127.0.0.1:8000";
const STATUS_POLL_INTERVAL = 5 * 60 * 1000;

type Stock = {
  symbol: string;
  date: string;
  close: number;
  return_20d: number | null;
  return_zscore: number | null;
  volume_ratio: number | null;
};

type MarketRegime = {
  symbol: string;
  as_of: string;
  regime: string;
  close: number;
  sma50: number;
  sma200: number;
  realized_volatility_20d_annualized: number;
};

type HistoryPoint = {
  date: string;
  close: number;
  volume: number;
  nifty_close: number | null;
};

type DataStatus = {
  latest_market_date: string;
  last_refresh_at: string;
  symbols: number;
  rows: number;
};

type Filters = {
  minReturn: string;
  minZscore: string;
  minVolume: string;
};

type BacktestMetric = {
  sample_size: number;
  mean_return: number | null;
  median_return: number | null;
  win_rate: number | null;
};

type BacktestHorizon = {
  stock: BacktestMetric;
  benchmark: BacktestMetric;
  excess_return: BacktestMetric;
};

type BacktestResult = {
  signal_count: number;
  date_start: string;
  date_end: string;
  thresholds: {
    min_return_20d: number | null;
    min_zscore: number | null;
    min_volume_ratio: number | null;
  };
  results: Record<string, BacktestHorizon>;
  methodology: string;
};

const EMPTY_FILTERS: Filters = {
  minReturn: "",
  minZscore: "",
  minVolume: "",
};

export default function Home() {
  const [stocks, setStocks] = useState<Stock[]>([]);
  const [regime, setRegime] = useState<MarketRegime | null>(null);

  const [selectedSymbol, setSelectedSymbol] = useState("");
  const [history, setHistory] = useState<HistoryPoint[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);

  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [historyError, setHistoryError] = useState("");

  const [dataStatus, setDataStatus] = useState<DataStatus | null>(null);
  const [statusError, setStatusError] = useState("");
  const [lastCheckedAt, setLastCheckedAt] = useState<string | null>(null);

  const [backtest, setBacktest] = useState<BacktestResult | null>(null);
  const [backtestLoading, setBacktestLoading] = useState(false);
  const [backtestError, setBacktestError] = useState("");

  // Keep the latest filter values available to the polling effect.
  const filtersRef = useRef(filters);
  filtersRef.current = filters;

  async function fetchRegime() {
    try {
      const response = await fetch(`${API}/api/regime`);
      if (!response.ok) throw new Error("Could not load market regime.");

      setRegime(await response.json());
    } catch {
      setError("Cannot connect to the backend. Check that FastAPI is running.");
    }
  }

  async function fetchStocks(nextFilters: Filters = filtersRef.current) {
    setLoading(true);
    setError("");

    try {
      const params = new URLSearchParams();

      if (nextFilters.minReturn !== "") {
        params.set(
          "min_return_20d",
          String(Number(nextFilters.minReturn) / 100),
        );
      }

      if (nextFilters.minZscore !== "") {
        params.set("min_zscore", nextFilters.minZscore);
      }

      if (nextFilters.minVolume !== "") {
        params.set("min_volume_ratio", nextFilters.minVolume);
      }

      const response = await fetch(
        `${API}/api/screener?${params.toString()}`,
      );

      if (!response.ok) throw new Error("Screener request failed.");

      const data = await response.json();
      setStocks(data.results);
    } catch {
      setError("Could not load stocks. Check that the backend is running.");
    } finally {
      setLoading(false);
    }
  }

  async function fetchDataStatus(): Promise<DataStatus | null> {
    try {
      const response = await fetch(`${API}/api/data-status`, {
        cache: "no-store",
      });

      if (!response.ok) {
        throw new Error("Could not retrieve data status.");
      }

      const status: DataStatus = await response.json();

      setDataStatus(status);
      setStatusError("");
      setLastCheckedAt(new Date().toISOString());

      return status;
    } catch {
      setStatusError("Data status unavailable. Check the backend connection.");
      setLastCheckedAt(new Date().toISOString());
      return null;
    }
  }

  async function runBacktest(nextFilters: Filters = filtersRef.current) {
    setBacktestLoading(true);
    setBacktestError("");

    try {
      const params = new URLSearchParams();

      if (nextFilters.minReturn !== "") {
        params.set(
          "min_return_20d",
          String(Number(nextFilters.minReturn) / 100),
        );
      }

      if (nextFilters.minZscore !== "") {
        params.set("min_zscore", nextFilters.minZscore);
      }

      if (nextFilters.minVolume !== "") {
        params.set("min_volume_ratio", nextFilters.minVolume);
      }

      const response = await fetch(
        `${API}/api/backtest?${params.toString()}`,
      );

      if (!response.ok) {
        const detail = await response.json().catch(() => null);
        throw new Error(detail?.detail || "Backtest request failed.");
      }

      setBacktest(await response.json());
    } catch (err) {
      setBacktestError(
        err instanceof Error
          ? err.message
          : "Could not load backtest results.",
      );
    } finally {
      setBacktestLoading(false);
    }
  }

  async function selectStock(symbol: string) {
    setSelectedSymbol(symbol);
    setHistory([]);
    setHistoryLoading(true);
    setHistoryError("");

    try {
      const response = await fetch(
        `${API}/api/stock/${encodeURIComponent(symbol)}/history?days=126`,
      );

      if (!response.ok) throw new Error();

      const data = await response.json();
      setHistory(data.history);
    } catch {
      setHistoryError(`Could not load historical data for ${symbol}.`);
    } finally {
      setHistoryLoading(false);
    }
  }

  useEffect(() => {
    void fetchRegime();
    void fetchStocks(EMPTY_FILTERS);
    void fetchDataStatus();

    let previousSignature: string | null = null;
    let requestInProgress = false;

    async function checkForUpdates() {
      if (requestInProgress) return;

      requestInProgress = true;

      try {
        const status = await fetchDataStatus();

        if (!status) return;

        const signature = [
          status.latest_market_date,
          status.last_refresh_at,
          status.rows,
        ].join("|");

        // Establish the initial baseline without reloading the page data.
        if (previousSignature === null) {
          previousSignature = signature;
          return;
        }

        // A new data date, file refresh time, or row count triggers a reload.
        if (signature !== previousSignature) {
          previousSignature = signature;

          void fetchStocks(filtersRef.current);
          void fetchRegime();
        }
      } finally {
        requestInProgress = false;
      }
    }

    const intervalId = window.setInterval(
      () => void checkForUpdates(),
      STATUS_POLL_INTERVAL,
    );

    return () => window.clearInterval(intervalId);
  }, []);

  function updateFilter(key: keyof Filters, value: string) {
    setFilters((previous) => ({ ...previous, [key]: value }));
  }

  function resetFilters() {
    setFilters(EMPTY_FILTERS);
    void fetchStocks(EMPTY_FILTERS);
  }

  const formatPercent = (value: number | null) =>
    value == null ? "—" : `${(value * 100).toFixed(2)}%`;

  const formatNumber = (value: number | null, digits = 2) =>
    value == null ? "—" : value.toFixed(digits);

  const formatDateTime = (value: string | null) => {
    if (!value) return "—";

    const date = new Date(value);

    if (Number.isNaN(date.getTime())) return value;

    return date.toLocaleString("en-IN", {
      dateStyle: "medium",
      timeStyle: "short",
      timeZone: "Asia/Kolkata",
    });
  };

  const chartData = history.map((point, index, points) => {
    const start = Math.max(0, index - 19);
    const window = points.slice(start, index + 1);

    const sma20 =
      window.length === 20
        ? window.reduce((sum, item) => sum + item.close, 0) / 20
        : null;

    return {
      ...point,
      date: String(point.date).slice(0, 10),
      sma20,
    };
  });

  const firstStockPoint = chartData[0];
  const firstCommonPoint = chartData.find(
    (point) => point.nifty_close != null,
  );

  const firstPrice = firstStockPoint?.close;
  const firstNifty = firstCommonPoint?.nifty_close;

  const performanceData = chartData.map((point) => ({
    ...point,
    stockPerformance:
      firstPrice != null && firstPrice !== 0
        ? (point.close / firstPrice - 1) * 100
        : null,
    niftyPerformance:
      firstNifty != null &&
      firstNifty !== 0 &&
      point.nifty_close != null
        ? (point.nifty_close / firstNifty - 1) * 100
        : null,
  }));

  return (
    <main className="min-h-screen bg-slate-950 px-4 py-8 text-slate-100 sm:px-8">
      <div className="mx-auto max-w-7xl">
        <header className="mb-8">
          <p className="mb-2 text-sm font-medium uppercase tracking-[0.25em] text-cyan-400">
            Market Research
          </p>

          <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">
            Statistical Stock Screener
          </h1>

          <p className="mt-3 text-slate-400">
            Screen Indian equities using momentum, return anomalies, and volume.
          </p>
        </header>

        {/* Data freshness */}
        <section className="mb-8 rounded-2xl border border-slate-800 bg-slate-900 p-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="font-semibold">Data Status</h2>
              <p className="mt-1 text-sm text-slate-400">
                Automatically checking for dataset updates every five minutes.
              </p>
            </div>

            <span
              className={`rounded-full px-3 py-1 text-xs font-medium ${
                statusError
                  ? "bg-red-950 text-red-300"
                  : dataStatus
                    ? "bg-emerald-950 text-emerald-300"
                    : "bg-slate-800 text-slate-300"
              }`}
            >
              {statusError
                ? "Status unavailable"
                : dataStatus
                  ? "Connected"
                  : "Checking..."}
            </span>
          </div>

          {statusError ? (
            <p className="mt-4 text-sm text-red-300">{statusError}</p>
          ) : dataStatus ? (
            <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <Metric
                label="Latest Market Date"
                value={String(dataStatus.latest_market_date).slice(0, 10)}
              />

              <Metric
                label="Last Dataset Refresh"
                value={formatDateTime(dataStatus.last_refresh_at)}
              />

              <Metric
                label="Symbols"
                value={dataStatus.symbols.toLocaleString("en-IN")}
              />

              <Metric
                label="Price Records"
                value={dataStatus.rows.toLocaleString("en-IN")}
              />
            </div>
          ) : (
            <p className="mt-4 text-sm text-slate-400">
              Loading dataset information...
            </p>
          )}

          <p className="mt-4 text-xs text-slate-500">
            Last status check: {formatDateTime(lastCheckedAt)}. The latest
            market date and last file refresh time are different measurements.
          </p>
        </section>

        {/* Market overview */}
        <section className="mb-8 rounded-2xl border border-slate-800 bg-slate-900 p-6">
          <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
            <h2 className="text-lg font-semibold">Market Overview</h2>

            <span className="text-sm text-slate-400">
              {regime
                ? `As of ${String(regime.as_of).slice(0, 10)}`
                : "Loading market data..."}
            </span>
          </div>

          {regime && (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <Metric
                label="NIFTY 50 Regime"
                value={regime.regime.replaceAll("_", " ")}
              />

              <Metric
                label="NIFTY 50 Close"
                value={regime.close.toLocaleString("en-IN", {
                  maximumFractionDigits: 2,
                })}
              />

              <Metric
                label="50-Day SMA"
                value={regime.sma50.toLocaleString("en-IN", {
                  maximumFractionDigits: 2,
                })}
              />

              <Metric
                label="20-Day Annualized Volatility"
                value={formatPercent(
                  regime.realized_volatility_20d_annualized,
                )}
              />
            </div>
          )}
        </section>

        {/* Screening filters */}
        <section className="mb-8 rounded-2xl border border-slate-800 bg-slate-900 p-6">
          <h2 className="mb-5 text-lg font-semibold">Screening Criteria</h2>

          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            <Filter
              label="Minimum 20-Day Return (%)"
              value={filters.minReturn}
              onChange={(value) => updateFilter("minReturn", value)}
              placeholder="e.g. 5"
            />

            <Filter
              label="Minimum Return Z-Score"
              value={filters.minZscore}
              onChange={(value) => updateFilter("minZscore", value)}
              placeholder="e.g. 2"
            />

            <Filter
              label="Minimum Volume Ratio"
              value={filters.minVolume}
              onChange={(value) => updateFilter("minVolume", value)}
              placeholder="e.g. 1.5"
            />
          </div>

          <div className="mt-6 flex flex-wrap gap-3">
            <button
              onClick={() => void fetchStocks()}
              disabled={loading}
              className="rounded-lg bg-cyan-500 px-5 py-2.5 font-semibold text-slate-950 transition hover:bg-cyan-400 disabled:opacity-50"
            >
              {loading ? "Screening..." : "Apply Filters"}
            </button>

            <button
              onClick={resetFilters}
              disabled={loading}
              className="rounded-lg border border-slate-700 px-5 py-2.5 font-medium text-slate-300 transition hover:bg-slate-800 disabled:opacity-50"
            >
              Reset
            </button>
          </div>
        </section>

        {/* Backtest dashboard */}
        <section className="mb-8 rounded-2xl border border-slate-800 bg-slate-900 p-6">
          <div className="mb-5 flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-sm font-medium uppercase tracking-[0.2em] text-cyan-400">
                Strategy Research
              </p>

              <h2 className="mt-1 text-xl font-semibold">
                Backtest Dashboard
              </h2>

              <p className="mt-2 max-w-3xl text-sm text-slate-400">
                Test how stocks matching the current screening thresholds
                performed historically.
              </p>
            </div>

            <button
              onClick={() => void runBacktest()}
              disabled={backtestLoading}
              className="rounded-lg bg-cyan-500 px-5 py-2.5 font-semibold text-slate-950 transition hover:bg-cyan-400 disabled:opacity-50"
            >
              {backtestLoading ? "Running Backtest..." : "Run Backtest"}
            </button>
          </div>

          <div className="mb-5 rounded-xl border border-slate-800 bg-slate-950/70 p-4">
            <p className="text-sm font-medium text-slate-200">
              Thresholds used
            </p>

            <div className="mt-3 grid gap-3 sm:grid-cols-3">
              <div>
                <p className="text-xs text-slate-500">
                  Minimum 20-day return
                </p>
                <p className="mt-1 font-semibold tabular-nums">
                  {filters.minReturn === ""
                    ? "No minimum"
                    : `${filters.minReturn}%`}
                </p>
              </div>

              <div>
                <p className="text-xs text-slate-500">
                  Minimum return Z-score
                </p>
                <p className="mt-1 font-semibold tabular-nums">
                  {filters.minZscore === "" ? "No minimum" : filters.minZscore}
                </p>
              </div>

              <div>
                <p className="text-xs text-slate-500">
                  Minimum volume ratio
                </p>
                <p className="mt-1 font-semibold tabular-nums">
                  {filters.minVolume === ""
                    ? "No minimum"
                    : `${filters.minVolume}x`}
                </p>
              </div>
            </div>
          </div>

          {backtestError && (
            <p className="mb-5 rounded-lg border border-red-900 bg-red-950/40 p-4 text-sm text-red-300">
              {backtestError}
            </p>
          )}

          {!backtest && !backtestLoading && !backtestError && (
            <div className="rounded-xl border border-dashed border-slate-700 p-8 text-center">
              <p className="font-medium text-slate-200">
                Ready to test your criteria
              </p>
              <p className="mt-2 text-sm text-slate-400">
                Click Run Backtest to calculate historical statistics.
              </p>
            </div>
          )}

          {backtestLoading && (
            <p className="py-8 text-center text-slate-400">
              Calculating historical results...
            </p>
          )}

          {backtest && !backtestLoading && (
            <>
              <div className="mb-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                <Metric
                  label="Historical Signals"
                  value={backtest.signal_count.toLocaleString("en-IN")}
                />
                <Metric label="Data Start" value={backtest.date_start} />
                <Metric label="Data End" value={backtest.date_end} />
              </div>

              <div className="overflow-x-auto rounded-xl border border-slate-800">
                <table className="w-full min-w-[760px] text-left text-sm">
                  <thead className="bg-slate-800/70 text-slate-300">
                    <tr>
                      <th className="px-4 py-3 font-medium">Horizon</th>
                      <th className="px-4 py-3 text-right font-medium">
                        Group
                      </th>
                      <th className="px-4 py-3 text-right font-medium">
                        Samples
                      </th>
                      <th className="px-4 py-3 text-right font-medium">
                        Mean Return
                      </th>
                      <th className="px-4 py-3 text-right font-medium">
                        Median Return
                      </th>
                      <th className="px-4 py-3 text-right font-medium">
                        Win Rate
                      </th>
                    </tr>
                  </thead>

                  <tbody className="divide-y divide-slate-800">
                    {(["1d", "5d"] as const).map((horizon) => {
                      const result = backtest.results[horizon];
                      if (!result) return null;

                      const rows = [
                        { label: "Stock", metric: result.stock },
                        { label: "NIFTY 50", metric: result.benchmark },
                        {
                          label: "Excess return",
                          metric: result.excess_return,
                        },
                      ];

                      return rows.map((row, index) => (
                        <tr
                          key={`${horizon}-${row.label}`}
                          className={
                            row.label === "Excess return"
                              ? "bg-slate-800/30"
                              : ""
                          }
                        >
                          {index === 0 && (
                            <td
                              rowSpan={3}
                              className="border-r border-slate-800 px-4 py-3 align-top font-semibold text-cyan-300"
                            >
                              {horizon === "1d" ? "1 day" : "5 days"}
                            </td>
                          )}

                          <td className="px-4 py-3 text-right">
                            {row.label}
                          </td>

                          <td className="px-4 py-3 text-right tabular-nums text-slate-300">
                            {row.metric.sample_size.toLocaleString("en-IN")}
                          </td>

                          <td
                            className={`px-4 py-3 text-right tabular-nums ${
                              (row.metric.mean_return ?? 0) >= 0
                                ? "text-emerald-400"
                                : "text-red-400"
                            }`}
                          >
                            {formatPercent(row.metric.mean_return)}
                          </td>

                          <td
                            className={`px-4 py-3 text-right tabular-nums ${
                              (row.metric.median_return ?? 0) >= 0
                                ? "text-emerald-400"
                                : "text-red-400"
                            }`}
                          >
                            {formatPercent(row.metric.median_return)}
                          </td>

                          <td className="px-4 py-3 text-right tabular-nums text-slate-300">
                            {formatPercent(row.metric.win_rate)}
                          </td>
                        </tr>
                      ));
                    })}
                  </tbody>
                </table>
              </div>

              <div className="mt-5 rounded-xl border border-amber-900/70 bg-amber-950/20 p-4">
                <p className="font-medium text-amber-200">
                  Interpret results cautiously
                </p>
                <p className="mt-2 text-sm leading-6 text-slate-300">
                  {backtest.methodology} This is a historical signal study, not
                  a live trading simulation. It does not yet account for
                  execution timing, transaction costs, slippage, or a separate
                  out-of-sample test. Signals may overlap, so observations are
                  not necessarily independent.
                </p>
              </div>
            </>
          )}
        </section>

        {/* Screening results */}
        <section className="mb-8 overflow-hidden rounded-2xl border border-slate-800 bg-slate-900">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 px-6 py-5">
            <h2 className="text-lg font-semibold">Screening Results</h2>
            <span className="text-sm text-slate-400">
              {stocks.length} stocks found
            </span>
          </div>

          {error && (
            <p className="m-6 rounded-lg border border-red-900 bg-red-950/40 p-4 text-sm text-red-300">
              {error}
            </p>
          )}

          <div className="overflow-x-auto">
            <table className="w-full min-w-[750px] text-left text-sm">
              <thead className="bg-slate-800/60 text-slate-400">
                <tr>
                  {[
                    "Symbol",
                    "Latest Close (₹)",
                    "20-Day Return",
                    "Return Z-Score",
                    "Volume Ratio",
                    "Date",
                  ].map((heading, index) => (
                    <th
                      key={heading}
                      className={`px-6 py-4 font-medium ${
                        index > 0 ? "text-right" : ""
                      }`}
                    >
                      {heading}
                    </th>
                  ))}
                </tr>
              </thead>

              <tbody className="divide-y divide-slate-800">
                {stocks.map((stock) => (
                  <tr
                    key={stock.symbol}
                    onClick={() => void selectStock(stock.symbol)}
                    title={`View ${stock.symbol} price chart`}
                    className={`cursor-pointer transition hover:bg-slate-800/70 ${
                      selectedSymbol === stock.symbol ? "bg-cyan-950/40" : ""
                    }`}
                  >
                    <td className="px-6 py-4 font-semibold text-cyan-300">
                      {stock.symbol}
                    </td>

                    <td className="px-6 py-4 text-right tabular-nums">
                      {stock.close.toLocaleString("en-IN", {
                        minimumFractionDigits: 2,
                        maximumFractionDigits: 2,
                      })}
                    </td>

                    <td
                      className={`px-6 py-4 text-right font-medium tabular-nums ${
                        (stock.return_20d ?? 0) >= 0
                          ? "text-emerald-400"
                          : "text-red-400"
                      }`}
                    >
                      {formatPercent(stock.return_20d)}
                    </td>

                    <td className="px-6 py-4 text-right tabular-nums">
                      {formatNumber(stock.return_zscore)}
                    </td>

                    <td className="px-6 py-4 text-right tabular-nums">
                      {formatNumber(stock.volume_ratio)}x
                    </td>

                    <td className="px-6 py-4 text-right text-slate-400">
                      {String(stock.date).slice(0, 10)}
                    </td>
                  </tr>
                ))}

                {!loading && stocks.length === 0 && !error && (
                  <tr>
                    <td
                      colSpan={6}
                      className="px-6 py-12 text-center text-slate-400"
                    >
                      No stocks match these criteria. Try relaxing the filters.
                    </td>
                  </tr>
                )}

                {loading && (
                  <tr>
                    <td
                      colSpan={6}
                      className="px-6 py-12 text-center text-slate-400"
                    >
                      Loading screening results...
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          <p className="border-t border-slate-800 px-6 py-4 text-xs text-slate-500">
            Click any stock row to inspect its historical performance. These
            metrics are historical indicators, not investment recommendations.
          </p>
        </section>

        {/* Selected stock charts */}
        {selectedSymbol && (
          <section className="mb-8 rounded-2xl border border-slate-800 bg-slate-900 p-6">
            <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-sm font-medium text-cyan-400">
                  STOCK DETAIL
                </p>
                <h2 className="mt-1 text-2xl font-bold">{selectedSymbol}</h2>
                <p className="mt-1 text-sm text-slate-400">
                  Approximately six months of trading sessions
                </p>
              </div>

              <button
                onClick={() => {
                  setSelectedSymbol("");
                  setHistory([]);
                  setHistoryError("");
                }}
                className="rounded-lg border border-slate-700 px-4 py-2 text-sm text-slate-300 hover:bg-slate-800"
              >
                Close chart
              </button>
            </div>

            {historyLoading ? (
              <p className="py-12 text-center text-slate-400">
                Loading historical prices...
              </p>
            ) : historyError ? (
              <p className="rounded-lg border border-red-900 bg-red-950/40 p-4 text-sm text-red-300">
                {historyError}
              </p>
            ) : chartData.length > 0 ? (
              <>
                <h3 className="mb-3 font-medium">
                  Closing Price and 20-Day SMA (₹)
                </h3>

                <div className="h-80 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <ComposedChart data={chartData}>
                      <CartesianGrid
                        stroke="#334155"
                        strokeDasharray="3 3"
                      />
                      <XAxis
                        dataKey="date"
                        tick={{ fill: "#94a3b8", fontSize: 11 }}
                        minTickGap={35}
                      />
                      <YAxis
                        domain={["auto", "auto"]}
                        tick={{ fill: "#94a3b8", fontSize: 11 }}
                      />
                      <Tooltip
                        labelStyle={{ color: "#e2e8f0" }}
                        contentStyle={{
                          backgroundColor: "#0f172a",
                          border: "1px solid #334155",
                          borderRadius: 8,
                        }}
                        formatter={(value, name) => [
                          value == null
                            ? "—"
                            : Number(value).toLocaleString("en-IN", {
                                maximumFractionDigits: 2,
                              }),
                          name,
                        ]}
                      />
                      <Line
                        type="monotone"
                        dataKey="close"
                        name="Stock close"
                        stroke="#22d3ee"
                        dot={false}
                        strokeWidth={2}
                        connectNulls
                      />
                      <Line
                        type="monotone"
                        dataKey="sma20"
                        name="20-Day SMA"
                        stroke="#fbbf24"
                        dot={false}
                        strokeWidth={2}
                        connectNulls
                      />
                    </ComposedChart>
                  </ResponsiveContainer>
                </div>

                <p className="mt-2 text-xs text-slate-500">
                  Cyan: daily close. Yellow: 20-session simple moving average.
                </p>

                <h3 className="mb-3 mt-8 font-medium">
                  Stock vs NIFTY 50 — Cumulative Return (%)
                </h3>

                <div className="h-80 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <ComposedChart data={performanceData}>
                      <CartesianGrid
                        stroke="#334155"
                        strokeDasharray="3 3"
                      />
                      <XAxis
                        dataKey="date"
                        tick={{ fill: "#94a3b8", fontSize: 11 }}
                        minTickGap={35}
                      />
                      <YAxis tick={{ fill: "#94a3b8", fontSize: 11 }} />
                      <Tooltip
                        labelStyle={{ color: "#e2e8f0" }}
                        contentStyle={{
                          backgroundColor: "#0f172a",
                          border: "1px solid #334155",
                          borderRadius: 8,
                        }}
                        formatter={(value, name) => [
                          value == null
                            ? "—"
                            : `${Number(value).toFixed(2)}%`,
                          name,
                        ]}
                      />
                      <Line
                        type="monotone"
                        dataKey="stockPerformance"
                        name={selectedSymbol}
                        stroke="#22d3ee"
                        dot={false}
                        strokeWidth={2}
                        connectNulls
                      />
                      <Line
                        type="monotone"
                        dataKey="niftyPerformance"
                        name="NIFTY 50"
                        stroke="#fbbf24"
                        dot={false}
                        strokeWidth={2}
                        connectNulls
                      />
                    </ComposedChart>
                  </ResponsiveContainer>
                </div>

                <h3 className="mb-3 mt-8 font-medium">Trading Volume</h3>

                <div className="h-64 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <ComposedChart data={chartData}>
                      <CartesianGrid
                        stroke="#334155"
                        strokeDasharray="3 3"
                      />
                      <XAxis
                        dataKey="date"
                        tick={{ fill: "#94a3b8", fontSize: 11 }}
                        minTickGap={35}
                      />
                      <YAxis tick={{ fill: "#94a3b8", fontSize: 11 }} />
                      <Tooltip
                        labelStyle={{ color: "#e2e8f0" }}
                        contentStyle={{
                          backgroundColor: "#0f172a",
                          border: "1px solid #334155",
                          borderRadius: 8,
                        }}
                        formatter={(value) => [
                          value == null
                            ? "—"
                            : Number(value).toLocaleString("en-IN"),
                          "Volume",
                        ]}
                      />
                      <Bar dataKey="volume" name="Volume" fill="#818cf8" />
                    </ComposedChart>
                  </ResponsiveContainer>
                </div>
              </>
            ) : (
              <p className="py-12 text-center text-slate-400">
                No historical data available for this stock.
              </p>
            )}
          </section>
        )}

        <footer className="pb-4 text-center text-xs text-slate-500">
          Data is based on the locally stored historical price dataset.
          Indicators describe past market behavior and do not guarantee future
          performance.
        </footer>
      </div>
    </main>
  );
}

function Metric({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-xl bg-slate-800/70 p-4">
      <p className="text-sm text-slate-400">{label}</p>
      <p className="mt-2 text-xl font-semibold capitalize">{value}</p>
    </div>
  );
}

function Filter({
  label,
  value,
  onChange,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
}) {
  return (
    <label className="text-sm text-slate-300">
      {label}
      <input
        type="number"
        step="0.1"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        className="mt-2 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2.5 text-white outline-none focus:border-cyan-500"
      />
    </label>
  );
}