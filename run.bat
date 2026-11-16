@echo off
setlocal
chcp 65001 >nul

if exist "%~dp0.venv\Scripts\python.exe" (
    "%~dp0.venv\Scripts\python.exe" "%~dp0cherrytale.py" %*
) else (
    python "%~dp0cherrytale.py" %*
)
