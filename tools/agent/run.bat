@echo off
cd /d %~dp0
if not exist agent.env (
  copy agent.env.example agent.env >nul
  echo Fill in agent.env first, then run this again.
  notepad agent.env
  exit /b
)
if not exist .venv python -m venv .venv
.venv\Scripts\python -m pip install -q httpx
.venv\Scripts\python agent.py
pause
