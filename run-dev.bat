@echo off
REM PhotoGenius AI - Development Server Launcher
REM Automatically kills existing processes and starts fresh

echo ========================================
echo PhotoGenius AI - Development Server
echo ========================================
echo.

REM Add pnpm to PATH for this session
set PATH=%PATH%;C:\Users\dell\AppData\Roaming\npm

REM Kill existing Python processes to free ports
echo [1/4] Cleaning up existing processes...
taskkill /F /IM python.exe >nul 2>&1
timeout /t 2 /nobreak >nul
echo       Done!
echo.

REM Kill Node processes
taskkill /F /IM node.exe >nul 2>&1
timeout /t 1 /nobreak >nul

echo [2/4] Generating Prisma client...
cd packages\database
pnpm run build
cd ..\..
echo       Done!
echo.

echo [3/4] Starting development servers...
echo       This will start:
echo       - Frontend at http://localhost:3002
echo       - API at http://localhost:8000
echo       - AI Service at http://localhost:8001
echo.

REM Run development server
echo [4/4] Running pnpm dev...
echo.
pnpm run dev

pause
