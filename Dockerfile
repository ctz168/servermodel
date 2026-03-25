# 统一分布式推理系统 - Docker 镜像
# 
# 构建方法:
#   docker build -t unified-inference .
#
# 运行方法:
#   docker run -d -p 8080:8080 --gpus all unified-inference
#

FROM python:3.10-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 复制应用代码
COPY core/node_unified_complete.py .
COPY ui/ ./ui/

# 设置环境变量
ENV HF_ENDPOINT=https://hf-mirror.com
ENV PYTHONUNBUFFERED=1

# 暴露端口
EXPOSE 5000 8080

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# 启动命令
CMD ["python", "node_unified_complete.py", "--host", "0.0.0.0", "--api-host", "0.0.0.0"]
