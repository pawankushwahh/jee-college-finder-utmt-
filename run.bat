@echo off
cd /d "%~dp0"
echo.
echo  Disha - JEE College Recommender
echo  ==============================
echo.
echo  Installing dependencies (if needed)...
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo  ERROR: Python or pip not found. Install Python 3.12+ from python.org
  pause
  exit /b 1
)
echo.
echo  Starting server...
echo  Open in browser: http://127.0.0.1:8000/
echo  Press Ctrl+C to stop.
echo.
python main.py
pause
