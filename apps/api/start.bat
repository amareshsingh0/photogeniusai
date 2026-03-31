@echo off
cd /d "%~dp0"
echo Killing old process on port 8003...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8003 "') do taskkill /F /PID %%a 2>nul
timeout /t 2 /nobreak >nul
echo Clearing Python cache...
for /r . %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d"
echo Starting PhotoGenius API...
python -m uvicorn app.main:app --host 0.0.0.0 --port 8003 --env-file .env.local --reload
pause
