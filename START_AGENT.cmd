@echo off
setlocal
python "%~dp0scripts\start_agent.py" %*
exit /b %ERRORLEVEL%