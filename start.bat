@echo off
chcp 65001 >nul
setlocal
set PY=C:\Users\admin\.workbuddy\binaries\python\envs\default\Scripts\python.exe
if not exist "%PY%" set PY=python

cd /d "%~dp0backend"
echo [1/2] 启动后端服务 http://127.0.0.1:8000 ...
start "ai-ads-backend" cmd /c ""%PY%" run.py"
timeout /t 4 >nul
echo [2/2] 打开工作台
start "" http://127.0.0.1:8000
echo.
echo 后端已在独立窗口启动，关闭该窗口即可停止服务。
endlocal
