# AI Sales Forecasting Frontend

This is the browser UI for the AI sales forecasting project. It works with the Python FastAPI backend in the project root.

## Run Backend

Install the updated dependencies if needed:

```bash
pip install -r requirements.txt
```

Start the Python API:

```bash
uvicorn api_server:app --reload
```

## Run Frontend

Open `frontend/index.html` in your browser. The forecast summary and 14-day forecast chart call the backend at `http://127.0.0.1:8000/api/forecast`.

## CSV Format

The dashboard expects these columns:

```csv
Date,Product,Region,Sales
2023-01-01,Laptop,North,1200
```

It also accepts lowercase column names and `Category` instead of `Product`.

## What It Does

- Upload sales CSV files
- Filter by product segment and date range
- Show revenue, average sales, highest sale, and row count
- Render sales trend and segment charts
- Generate a 14-day forecast from the Python backend
- Export forecast results as CSV
