# Indian Equity Stock Screener

A quantitative research platform for screening Indian equities using price-based technical indicators, market regime analysis, and historical backtesting.

The application combines a FastAPI backend with a Next.js dashboard to help explore stock price movements, identify unusual market activity, compare stocks against the NIFTY 50 benchmark, and evaluate screening conditions against historical data.

## Features

- **Stock Screener:** Filter stocks using configurable return, z-score, and volume-ratio thresholds.
- **Technical Indicators:** Analyze price trends and unusual movements using historical price and volume data.
- **Market Regime Analysis:** View market conditions using the NIFTY 50 benchmark.
- **Stock Analysis:** Inspect historical closing prices, moving averages, relative performance against the benchmark, and trading volume.
- **Historical Backtesting:** Evaluate screening signals using forward one-day and five-day returns, win rates, and benchmark-relative performance.
- **Automated Data Refresh:** Download and update daily price history using Yahoo Finance, with scheduled refresh jobs.
- **Data Status Monitoring:** Track the latest available market date, dataset refresh time, number of symbols, and total records.
- **Docker Support:** Run the FastAPI backend in a container with persistent access to the local price dataset.

## Tech Stack

**Backend**
- Python
- FastAPI
- Pandas and NumPy
- yfinance
- APScheduler

**Frontend**
- Next.js
- React
- TypeScript
- Tailwind CSS
- Recharts

**Infrastructure**
- Docker and Docker Compose
- CSV-based price storage
- Git and GitHub

## Architecture

The application follows a simple client-server architecture.

1. The data module downloads and maintains historical daily prices.
2. The backend loads the dataset and computes screening metrics, indicators, market regime information, and backtest results.
3. The FastAPI application exposes these calculations through REST API endpoints.
4. The Next.js frontend consumes the API and displays the results through tables, charts, and summary panels.

Historical prices are stored in `data/prices.csv`. When using Docker Compose, this directory is mounted into the backend container so the dataset remains outside the container's writable layer.

## Project Structure

```text
screener/
├── backend/
│   ├── main.py
│   ├── data.py
│   ├── indicators.py
│   ├── screener.py
│   ├── backtest.py
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   └── src/
│       └── app/
│           └── page.tsx
├── data/
│   └── prices.csv
├── compose.yaml
└── .dockerignore
```

The frontend directory also contains the standard Next.js configuration, package manifest, and other application files.

## Getting Started

### Prerequisites

- Python 3.11 or compatible version
- Node.js and npm
- Git
- Docker Desktop, if running the backend through Docker

### 1. Clone the repository

```bash
git clone <repository-url>
cd screener
```

Replace `<repository-url>` with the URL of your GitHub repository.

### 2. Set up the backend

Create and activate a virtual environment from the project root.

On Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
```

Start the API:

```powershell
cd backend
uvicorn main:app --reload
```

The API will be available at `http://localhost:8000`.

Interactive API documentation is available at `http://localhost:8000/docs`.

The backend expects the historical dataset at `data/prices.csv` in the project root. If the file is not present, initialize the dataset using the project's data module.

### 3. Set up the frontend

Open a separate terminal:

```powershell
cd frontend
npm install
npm run dev
```

The dashboard will be available at `http://localhost:3000`.

By default, the frontend must point to the URL where the FastAPI backend is running. Update the API configuration if the backend uses a different port.

## Running with Docker

The backend can be built and started using Docker Compose from the project root:

```bash
docker compose up --build -d
```

Check the container status and logs:

```bash
docker compose ps
docker compose logs -f backend
```

With the local configuration, the backend is exposed on port `8001` and listens on port `8000` inside the container.

The API documentation is available at `http://localhost:8001/docs`.

The Compose configuration mounts `./data` into `/app/data`, allowing the application to read and update the existing price dataset without relying on the container's writable layer for persistence.

To stop the services:

```bash
docker compose down
```

## API Endpoints

| Endpoint | Description |
|---|---|
| `GET /api/health` | Check API availability |
| `GET /api/regime` | Retrieve market regime information |
| `GET /api/screener` | Screen stocks using configurable thresholds |
| `GET /api/stock/{symbol}/history` | Retrieve historical data for a stock |
| `GET /api/backtest` | Evaluate historical screening signals |
| `GET /api/data-status` | Retrieve dataset status and refresh metadata |

The interactive API documentation provides the available query parameters and response schemas.

## Data and Methodology

The application uses daily price history downloaded through Yahoo Finance. The universe includes 49 individual stock symbols and the NIFTY 50 index as a benchmark.

Screening conditions use historical price and volume information. The backtesting module measures subsequent one-day and five-day returns for qualifying signals and compares stock performance with the benchmark.

The backtest is a historical signal evaluation rather than a complete trading simulation. Results should not be interpreted as live trading performance.

## Limitations

- The stock universe is a selected list of symbols and does not represent the complete Indian equity market.
- Data availability and update timing depend on the external data provider.
- The project currently uses CSV-based storage rather than a dedicated database.
- Backtesting does not fully model transaction costs, slippage, capital allocation, or portfolio-level risk.
- Historical results do not guarantee future performance.
- Automated refresh jobs require a running backend process and appropriate production scheduling and persistent storage configuration.

## Future Improvements

- Expand the stock universe and add fundamental data.
- Add sector-level comparisons and more screening criteria.
- Improve backtesting with transaction costs, position sizing, and portfolio-level metrics.
- Add a dedicated database for historical market data.
- Improve data validation, logging, and monitoring.
- Deploy the frontend and backend with production-specific configuration.

## Disclaimer

This project is intended for educational and research purposes. It does not provide investment advice or guarantee the accuracy or future performance of any screening signal. Always independently verify data and conduct your own research before making investment decisions.