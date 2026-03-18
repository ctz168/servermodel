@echo off
chcp 65001 >nul

echo.
echo 停止服务...

REM 查找并停止所有 python 进程运行 node_unified_complete.py
taskkill /f /im python.exe /fi "WINDOWTITLE eq node_unified*" >nul 2>&1

REM 更可靠的方法：通过 WMIC 查找并停止
for /f "tokens=2" %%i in ('wmic process where "commandline like '%%node_unified_complete%%'" get processid 2^>nul ^| findstr /r "[0-9]"') do (
    taskkill /f /pid %%i >nul 2>&1
)

echo [成功] 服务已停止
echo.

pause
