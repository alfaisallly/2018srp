@echo off
REM ============================================================
REM  Build a standalone Windows 11 executable for the
REM  Coarray MUSIC DOA Estimator.
REM
REM  Designer: Eng. Ahmed Majed / المهندس أحمد ماجد
REM
REM  Prerequisites (Windows 11):
REM    - Python 3.10+ (64-bit) from https://www.python.org  (tick "Add to PATH")
REM
REM  Just double-click this file (or run it in a terminal). It installs the
REM  dependencies and produces  dist\DOA_Estimator.exe
REM ============================================================

cd /d "%~dp0"

echo Installing dependencies...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt pyinstaller

echo Building executable...
python -m PyInstaller --noconfirm --clean --onefile --windowed ^
  --name DOA_Estimator ^
  --collect-all matplotlib ^
  doa_app.py

echo.
echo Done. The executable is at:  dist\DOA_Estimator.exe
pause
