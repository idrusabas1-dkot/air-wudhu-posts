@echo off
title Air Wudhu
cd /d "%~dp0ui"
chcp 65001 >nul
if "%UI_PORT%"=="" set UI_PORT=8600

rem UI sudah berjalan? cukup buka browser, jangan jalankan server kedua
netstat -ano | findstr /R /C:":%UI_PORT% .*LISTENING" >nul
if not errorlevel 1 (
  echo  Air Wudhu sudah berjalan di http://127.0.0.1:%UI_PORT% - membuka browser...
  start http://127.0.0.1:%UI_PORT%
  timeout /t 3 >nul
  exit /b 0
)

echo.
echo  Air Wudhu: http://127.0.0.1:%UI_PORT%
echo  Biarkan jendela ini terbuka selama memakai aplikasi.
echo.
start "" cmd /c "timeout /t 3 >nul & start http://127.0.0.1:%UI_PORT%"
"%~dp0..\.venv\Scripts\python.exe" app.py
pause
