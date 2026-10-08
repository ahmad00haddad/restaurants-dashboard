@echo off
cd /d %~dp0
pip install -q httpx playwright
python -m playwright install chromium
python harvest.py
pause
