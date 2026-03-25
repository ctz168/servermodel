@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo 启动分布式推理节点...
echo.

REM 设置UTF-8编码
set PYTHONIOENCODING=utf-8

REM 启动服务
start "分布式推理节点" python download/node_unified_complete.py --config config.json --auto

echo.
echo 等待服务启动...
timeout /t 15 /nobreak >nul

echo.
echo 测试API端点...
echo.

curl -s http://localhost:8080/health
echo.

curl -s http://localhost:8080/node/info
echo.

echo.
echo 测试推理API...
echo.

curl -s -X POST http://localhost:8080/v1/chat/completions ^
  -H "Content-Type: application/json" ^
  -d "{\"model\": \"Qwen/Qwen2.5-0.5B-Instruct\", \"messages\": [{\"role\": \"user\", \"content\": \"你好\"}], \"max_tokens\": 20}"

echo.
echo.
pause
