@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

REM 统一分布式推理系统 - 一键启动脚本 (Windows)
REM 使用方法: 双击运行 start.bat

REM 颜色定义（Windows 10+ 支持）
for /f %%i in ('echo prompt $E^| cmd') do set "ESC=%%i"
set "RED=!ESC![91m"
set "GREEN=!ESC![92m"
set "YELLOW=!ESC![93m"
set "BLUE=!ESC![94m"
set "NC=!ESC![0m"

REM 打印横幅
echo.
echo ============================================================
echo    统一分布式推理系统 - 一键启动
echo ============================================================
echo.

REM 检查 Python
echo [信息] 检查 Python 环境...

where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未找到 Python，请先安装 Python 3.8+
    echo [信息] 下载地址: https://www.python.org/downloads/
    echo [信息] 安装时请勾选 "Add Python to PATH"
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo [成功] Python 版本: %PYTHON_VERSION%

REM 检查 pip
echo [信息] 检查 pip...

python -m pip --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [警告] pip 未安装，正在安装...
    python -m ensurepip --upgrade
)

echo [成功] pip 已安装

REM 检查依赖
echo [信息] 检查依赖...

set NEED_INSTALL=0

python -c "import torch" >nul 2>&1
if %errorlevel% neq 0 (
    echo [警告] torch 未安装
    set NEED_INSTALL=1
)

python -c "import transformers" >nul 2>&1
if %errorlevel% neq 0 (
    echo [警告] transformers 未安装
    set NEED_INSTALL=1
)

python -c "import psutil" >nul 2>&1
if %errorlevel% neq 0 (
    echo [警告] psutil 未安装
    set NEED_INSTALL=1
)

if %NEED_INSTALL% equ 1 (
    echo [信息] 正在安装依赖...
    python -m pip install --upgrade pip -q
    python -m pip install torch transformers psutil -q -i https://pypi.tuna.tsinghua.edu.cn/simple
    echo [成功] 依赖安装完成
) else (
    echo [成功] 所有依赖已安装
)

REM 检查 GPU
echo [信息] 检查 GPU...

python -c "import torch; assert torch.cuda.is_available()" >nul 2>&1
if %errorlevel% equ 0 (
    for /f "delims=" %%i in ('python -c "import torch; print(torch.cuda.get_device_name(0))"') do set GPU_NAME=%%i
    for /f "delims=" %%i in ('python -c "import torch; print(int(torch.cuda.get_device_properties(0).total_memory / 1024**3))"') do set GPU_MEMORY=%%i
    echo [成功] 检测到 GPU: !GPU_NAME! (!GPU_MEMORY!GB)
    set DEVICE=cuda
    
    REM 根据显存选择模型
    if !GPU_MEMORY! geq 20 (
        set MODEL=Qwen/Qwen2.5-7B-Instruct
    ) else if !GPU_MEMORY! geq 10 (
        set MODEL=Qwen/Qwen2.5-1.5B-Instruct
    ) else (
        set MODEL=Qwen/Qwen2.5-0.5B-Instruct
    )
) else (
    echo [警告] 未检测到 GPU，将使用 CPU 模式
    echo [信息] 提示: CPU 模式速度较慢，建议使用 GPU
    set DEVICE=cpu
    set MODEL=Qwen/Qwen2.5-0.5B-Instruct
)

echo [成功] 选择模型: %MODEL%

REM 设置环境变量
echo [信息] 设置环境变量...
set HF_ENDPOINT=https://hf-mirror.com
echo [成功] 环境变量设置完成

REM 设置端口
set PORT=5000
set API_PORT=8080

REM 获取脚本所在目录
set SCRIPT_DIR=%~dp0
set MAIN_SCRIPT=%SCRIPT_DIR%download\node_unified_complete.py

REM 检查主程序是否存在
if not exist "%MAIN_SCRIPT%" (
    echo [错误] 主程序不存在: %MAIN_SCRIPT%
    pause
    exit /b 1
)

echo.
echo ============================================================
echo    服务启动中...
echo ============================================================
echo.
echo   模型:     %MODEL%
echo   通信端口: %PORT%
echo   API 端口: %API_PORT%
echo   设备:     %DEVICE%
echo.
echo   API 地址: http://localhost:%API_PORT%
echo   健康检查: http://localhost:%API_PORT%/health
echo.
echo ============================================================
echo   按 Ctrl+C 停止服务
echo ============================================================
echo.

REM 启动主程序
python "%MAIN_SCRIPT%" --port %PORT% --api-port %API_PORT% --model "%MODEL%" --auto

REM 如果程序退出，暂停以便查看错误信息
pause
