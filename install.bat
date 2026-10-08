@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo Устанавливаю зависимости из requirements.txt...
echo.

where python >nul 2>&1
if %errorlevel%==0 (
  python -m pip install -r requirements.txt
) else (
  py -3 -m pip install -r requirements.txt
)

if errorlevel 1 (
  echo.
  echo Не удалось установить зависимости.
  echo Нужен Python 3 с галочкой Add python.exe to PATH, либо лаунчер py.
  echo После этого запусти install.bat ещё раз.
  pause
  exit /b 1
)

echo.
echo Готово. Игру запускает play.bat.
pause
