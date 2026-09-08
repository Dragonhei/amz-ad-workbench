@echo off
chcp 65001 >nul
setlocal
REM 自动探测 python（兼容 python / python3，去掉了对特定虚拟环境的写死路径）
set PY=python
where python >nul 2>&1 || set PY=python3
where %PY% >nul 2>&1 || (
  echo [错误] 未检测到 Python，请先安装 Python 3.10+ 并加入 PATH。
  pause & exit /b 1
)

cd /d "%~dp0backend"
echo [1/2] 启动后端服务  http://127.0.0.1:8000
echo        首次运行前请先安装依赖： pip install -r requirements.txt
echo        如需演示数据（5 份示例报表）： python seed_data.py
start "ai-ads-backend" cmd /c "%PY% run.py"
timeout /t 4 >nul

echo [2/2] 打开工作台
start "" http://127.0.0.1:8000
echo.
echo 提示：
echo   - 完整前端界面需先构建：进入 frontend 目录执行  npm install ^&^& npm run build
echo   - 后端 API 健康检查： http://127.0.0.1:8000/api/health
echo   - 默认账号： admin/admin123（管理员）、 operator/123456（运营）
echo 后端已在独立窗口启动，关闭该窗口即可停止服务。
endlocal
