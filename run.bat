@echo off
rem Set DEBUG=1 to run with a console window that shows logs and errors.
rem With DEBUG=0 the app runs without a console; errors go to data\error.log
set DEBUG=0

cd /d "%~dp0"
if "%DEBUG%"=="1" (
    py -3.11 main.py
    pause
) else (
    start "" pyw -3.11 main.py
)
