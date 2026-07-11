@echo off
cd /d "%~dp0"
echo Starting AI Sales Forecasting backend...
echo.
echo Backend URL: http://127.0.0.1:8000
echo Keep this window open while using the frontend.
echo.
python -m uvicorn api_server:app --host 127.0.0.1 --port 8000
pause
