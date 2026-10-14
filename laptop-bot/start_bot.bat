@echo off
REM Double-click (or put a shortcut in shell:startup) to run the scheduler at login.
cd /d %~dp0
call .venv\Scripts\activate
python bot.py schedule
