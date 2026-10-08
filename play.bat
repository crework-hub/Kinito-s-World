@echo off
chcp 65001 >nul
cd /d "%~dp0"

where python >nul 2>&1
if %errorlevel%==0 (
  python kinito_park.py
) else (
  py -3 kinito_park.py
)

if errorlevel 1 (
  echo.
  echo Не удалось запустить игру.
  echo Сначала запусти install.bat в этой же папке.
  pause
)
