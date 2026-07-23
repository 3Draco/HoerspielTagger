@echo off
title HoerspielTag
cd /d "%~dp0"
echo ==================================================
echo   HoerspielTag - AI-Powered Audio Drama Tagger
echo ==================================================
echo.
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python konnte nicht gefunden werden.
    echo Bitte installiere Python und fuege es zum PATH hinzu.
    pause
    exit /b 1
)
echo Ueberpruefe Python-Abhaengigkeiten...
pip install -r requirements.txt
echo.
echo Starte HoerspielTag GUI...
python main.py
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] HoerspielTag wurde unerwartet beendet.
    pause
)
