# AI Sales Forecasting System

This project now uses a browser frontend with a Python FastAPI backend.

## Project Structure

```text
frontend/
  index.html      Browser dashboard
  styles.css      Dashboard styling
  app.js          Frontend logic and API calls

api_server.py     Python forecast API
start_backend.bat Windows helper to start the API
requirements.txt  Python dependencies
sales_data.csv    Sample sales data
sales_model.pkl   Existing trained model file
```

## Run the Project

1. Start the backend:

```bash
start_backend.bat
```

2. Keep the backend terminal open.

3. Open the frontend:

```text
frontend/index.html
```

If the backend is running, the dashboard status shows `Python API connected`.

## CSV Format

```csv
Date,Product,Region,Sales
2023-01-01,Laptop,North,1200
```
