# 统一分布式推理系统

> 🚀 **一键启动，开箱即用** - 无需复杂配置，打开即可运行大模型推理服务

## 📋 目录

- [快速开始](#-快速开始)
- [一键安装](#-一键安装)
- [使用方法](#-使用方法)
- [公网暴露（Ngrok）](#-公网暴露ngrok)
- [Web UI](#-web-ui)
- [Docker 部署](#-docker-部署)
- [API 接口](#-api-接口)
- [多节点集群](#-多节点集群)
- [常见问题](#-常见问题)

---

## 🚀 快速开始

### 方式一：一键启动（推荐）

**Windows 用户：**
```bash
# 双击运行
start.bat
```

**Linux/Mac 用户：**
```bash
# 添加执行权限并运行
chmod +x start.sh && ./start.sh
```

### 方式二：手动启动

```bash
# 1. 安装依赖
pip install torch transformers psutil

# 2. 启动服务
python download/node_unified_complete.py

# 3. 打开浏览器访问
# http://localhost:8080
```

---

## 📦 一键安装

### Windows

```batch
:: 运行安装脚本
install.bat
```

### Linux/Mac

```bash
# 运行安装脚本
chmod +x install.sh && ./install.sh
```

### 手动安装

```bash
# 创建虚拟环境（可选）
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# 安装依赖
pip install -r requirements.txt
```

---

## 🎯 使用方法

### 1. 最简单启动

```bash
python download/node_unified_complete.py
```

启动后访问：
- **API 地址**: http://localhost:8080
- **健康检查**: http://localhost:8080/health
- **状态查看**: http://localhost:8080/status

### 2. 自动模式选择

```bash
python download/node_unified_complete.py --auto
```

系统会自动检测你的硬件配置，选择最佳运行模式。

### 3. 指定模型

```bash
# 小模型（适合低配电脑）
python download/node_unified_complete.py --model "Qwen/Qwen2.5-0.5B-Instruct"

# 中等模型（适合 8GB+ 显存）
python download/node_unified_complete.py --model "Qwen/Qwen2.5-1.5B-Instruct"

# 大模型（适合 16GB+ 显存）
python download/node_unified_complete.py --model "Qwen/Qwen2.5-7B-Instruct"
```

### 4. 指定端口

```bash
python download/node_unified_complete.py --port 6000 --api-port 9000
```

### 5. 使用配置文件

系统支持通过 `config.json` 配置文件进行配置，配置优先级：**命令行 > 配置文件 > 默认值**。

**配置文件示例 (`config.json`)：**
```json
{
  "node": {
    "name": "my-node",
    "host": "0.0.0.0",
    "port": 5000,
    "api_host": "0.0.0.0",
    "api_port": 8080
  },
  "model": {
    "name": "Qwen/Qwen2.5-0.5B-Instruct",
    "cache_dir": "",
    "device": "auto",
    "precision": "auto",
    "max_workers": 2
  },
  "ngrok": {
    "enabled": true,
    "auth_token": "YOUR_NGROK_TOKEN",
    "region": "ap"
  },
  "paths": {
    "model_cache": "",
    "log_dir": "logs"
  },
  "cluster": {
    "seeds": ["192.168.1.100:5000"],
    "heartbeat_interval": 2.0
  }
}
```

**使用配置文件：**
```bash
# 默认读取当前目录的 config.json
python download/node_unified_complete.py

# 指定配置文件路径
python download/node_unified_complete.py --config /path/to/config.json

# 命令行参数会覆盖配置文件
python download/node_unified_complete.py --config config.json --port 6000
```

**配置文件字段说明：**

| 字段 | 说明 | 默认值 |
|------|------|--------|
| `node.name` | 节点名称 | 自动生成 |
| `node.host` | 节点主机 | 0.0.0.0 |
| `node.port` | 节点通信端口 | 5000 |
| `node.api_port` | API 服务端口 | 8080 |
| `model.name` | 模型名称 | Qwen/Qwen2.5-0.5B-Instruct |
| `model.cache_dir` | 模型缓存目录 | ~/.cache/huggingface |
| `ngrok.enabled` | 是否启用 ngrok | false |
| `ngrok.auth_token` | ngrok 认证令牌 | - |
| `ngrok.region` | ngrok 区域 | ap |
| `paths.model_cache` | 模型缓存路径 | ~/.cache/huggingface |
| `paths.log_dir` | 日志目录 | logs |

### 6. 公网暴露（Ngrok）

使用 ngrok 将服务暴露到公网，支持远程访问和多节点集群。

**安装 ngrok：**
```bash
pip install pyngrok
```

**获取 authtoken：**
1. 访问 https://dashboard.ngrok.com/get-started/your-authtoken
2. 注册/登录后获取 authtoken

**启动公网服务：**
```bash
# 方式一：命令行指定 token
python download/node_unified_complete.py --ngrok --ngrok-auth-token YOUR_TOKEN

# 方式二：使用环境变量
export NGROK_AUTHTOKEN=YOUR_TOKEN
python download/node_unified_complete.py --ngrok

# 指定区域（默认 ap - 亚太）
python download/node_unified_complete.py --ngrok --ngrok-auth-token YOUR_TOKEN --ngrok-region us
```

**启动后会显示：**
```
[Ngrok] 节点通信地址: tcp://0.tcp.ngrok.io:12345
[Ngrok] API 公网地址: https://abc123.ngrok.io
[Ngrok] 健康检查: https://abc123.ngrok.io/health
[Ngrok] Web UI: https://abc123.ngrok.io
```

**多节点集群（公网）：**
```bash
# 节点1（领导节点）
python download/node_unified_complete.py --ngrok --ngrok-auth-token YOUR_TOKEN

# 节点2（工作节点 - 在另一台机器上）
python download/node_unified_complete.py --seeds "0.tcp.ngrok.io:12345" --ngrok --ngrok-auth-token YOUR_TOKEN
```

**Ngrok 区域选项：**
- `us` - 美国
- `eu` - 欧洲
- `ap` - 亚太（默认）
- `au` - 澳大利亚
- `sa` - 南美
- `jp` - 日本
- `in` - 印度

---

## 🖥️ Web UI

启动服务后，打开浏览器访问：

```
http://localhost:8080
```

或使用独立的 Web UI 界面：

```bash
# 打开 UI 目录下的 index.html
open ui/index.html        # Mac
xdg-open ui/index.html    # Linux
start ui/index.html       # Windows
```

**Web UI 功能：**
- 💬 对话界面 - 直接与模型交互
- 📊 状态监控 - 实时查看节点状态
- 📡 API 文档 - 查看接口使用方法
- ⚙️ 设置配置 - 自定义 API 地址

---

## 🐳 Docker 部署

### 单节点部署

```bash
# 构建镜像
docker build -t unified-inference .

# 运行容器 (GPU)
docker run -d -p 8080:8080 --gpus all unified-inference

# 运行容器 (CPU)
docker run -d -p 8080:8080 unified-inference
```

### 多节点集群部署

```bash
# 启动 3 节点集群
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止集群
docker-compose down
```

---

## 🔌 API 接口

### OpenAI 兼容接口

系统完全兼容 OpenAI API 格式，可以直接替换 OpenAI 的 base_url 使用。

#### 聊天补全

```bash
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen/Qwen2.5-0.5B-Instruct",
    "messages": [
      {"role": "user", "content": "你好，请介绍一下自己"}
    ]
  }'
```

#### 文本补全

```bash
curl -X POST http://localhost:8080/v1/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen/Qwen2.5-0.5B-Instruct",
    "prompt": "人工智能是"
  }'
```

### Python 调用

```python
import requests

# 聊天补全
response = requests.post(
    "http://localhost:8080/v1/chat/completions",
    json={
        "model": "Qwen/Qwen2.5-0.5B-Instruct",
        "messages": [
            {"role": "user", "content": "你好"}
        ]
    }
)

print(response.json())
```

### 使用 OpenAI SDK

```python
from openai import OpenAI

# 只需修改 base_url
client = OpenAI(
    base_url="http://localhost:8080/v1",
    api_key="not-needed"  # 本地部署不需要 API Key
)

response = client.chat.completions.create(
    model="Qwen/Qwen2.5-0.5B-Instruct",
    messages=[
        {"role": "user", "content": "你好"}
    ]
)

print(response.choices[0].message.content)
```

---

## 🖥️ 多节点集群

### 快速启动集群

**节点 1（领导节点）：**
```bash
python download/node_unified_complete.py --port 5000 --api-port 8080
```

**节点 2（工作节点）：**
```bash
python download/node_unified_complete.py --port 5001 --api-port 8081 --seeds "localhost:5000"
```

**节点 3（工作节点）：**
```bash
python download/node_unified_complete.py --port 5002 --api-port 8082 --seeds "localhost:5000"
```

### 使用启动脚本

```bash
# 启动 3 节点集群
./scripts/start_cluster.sh 3

# 停止集群
./scripts/stop_cluster.sh
```

---

## ⚙️ 配置选项

### 命令行参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--port` | 5000 | 节点通信端口 |
| `--api-port` | 8080 | API 服务端口 |
| `--model` | Qwen/Qwen2.5-0.5B-Instruct | 模型名称 |
| `--mode` | data_parallel | 并行模式 |
| `--auto` | False | 自动选择模式 |
| `--seeds` | "" | 种子节点列表 |

### 并行模式

| 模式 | 说明 | 适用场景 |
|------|------|---------|
| `data_parallel` | 数据并行（负载均衡） | 内存充足，追求低延迟，多请求高吞吐 |
| `pipeline_parallel` | Pipeline 并行（模型分层） | 单节点显存不足，大模型，中等带宽 |
| `tensor_parallel` | Tensor 并行（张量切分） | 大模型，高带宽网络（开发中） |
| `hybrid` | 混合并行 | 大规模集群，最完整方案 |

#### 数据并行模式（默认）

**原理：** 每个节点加载完整模型，领导节点分发请求到空闲节点

**优势：**
- ✅ 实现简单，稳定可靠
- ✅ 提高吞吐量（同时处理多个请求）
- ✅ 故障恢复快（任何节点都能独立工作）

**限制：**
- ❌ 每个节点需要足够显存加载完整模型
- ❌ 单个请求不能跨节点协作

**启动方式：**
```bash
# 所有节点使用相同命令
python download/node_unified_complete.py --mode data_parallel
```

#### Pipeline 并行模式

**原理：** 模型按层切分到不同节点，请求依次流经各节点

```
节点A (0-12层)  →  节点B (13-24层)  →  节点C (25-36层)
    ↑                    ↑                    ↑
  输入               中间结果              输出
```

**优势：**
- ✅ 可以运行比单个节点显存更大的模型
- ✅ 单个请求由多节点协作完成
- ✅ 降低单节点显存需求

**限制：**
- ❌ 增加通信延迟
- ❌ 需要稳定网络连接

**启动方式：**
```bash
# 领导节点（阶段 0）
python download/node_unified_complete.py --mode pipeline_parallel --stages 3

# 工作节点（阶段 1, 2）
python download/node_unified_complete.py --mode pipeline_parallel --stages 3 --seeds "leader:5000"
```

**或通过配置文件：**
```json
{
  "parallel": {
    "mode": "pipeline_parallel",
    "pipeline_stages": 3
  }
}
```

#### 混合并行模式

**原理：** Pipeline 并行 + 数据并行

```
Pipeline 组 A: 节点1 → 节点2 → 节点3
Pipeline 组 B: 节点4 → 节点5 → 节点6
```

- 每个 Pipeline 组可以处理不同的请求（数据并行）
- 单个请求在一个 Pipeline 组内协作完成（Pipeline 并行）

**优势：**
- ✅ 兼具高吞吐量和大模型支持
- ✅ 最完整的分布式方案

**启动方式：**
```bash
python download/node_unified_complete.py --mode hybrid --dp 2 --pp 3
```

---

## 🔧 常见问题

### Q1: 端口被占用怎么办？

```bash
# 更换端口
python download/node_unified_complete.py --port 6000 --api-port 9000
```

### Q2: 内存不足怎么办？

```bash
# 使用更小的模型
python download/node_unified_complete.py --model "Qwen/Qwen2.5-0.5B-Instruct"

# 或者使用 CPU 模式（自动降级）
# 系统会自动检测并使用 CPU
```

### Q3: 模型下载失败？

```bash
# 使用国内镜像
export HF_ENDPOINT=https://hf-mirror.com
python download/node_unified_complete.py
```

### Q4: 如何查看日志？

```bash
# 启动时会自动打印日志到控制台
# 也可以重定向到文件
python download/node_unified_complete.py 2>&1 | tee server.log
```

### Q5: 如何停止服务？

```bash
# 按 Ctrl+C 停止
# 或者使用停止脚本
./stop.sh        # Linux/Mac
stop.bat         # Windows
```

### Q6: Ngrok 报错怎么办？

**错误：`pyngrok 未安装`**
```bash
pip install pyngrok
```

**错误：`Authentication failed`**
```bash
# 确保使用正确的 authtoken
# 访问 https://dashboard.ngrok.com/get-started/your-authtoken 获取
python download/node_unified_complete.py --ngrok --ngrok-auth-token YOUR_TOKEN
```

**错误：`Tunnel limit reached`**
```
# 免费账户同时只能运行 1 个隧道
# 需要关闭其他 ngrok 进程
pkill ngrok  # Linux/Mac
taskkill /f /im ngrok.exe  # Windows
```

### Q7: 如何在公网运行多节点集群？

```bash
# 1. 启动领导节点（带 ngrok）
python download/node_unified_complete.py --ngrok --ngrok-auth-token YOUR_TOKEN

# 2. 记录输出的节点通信地址，例如：tcp://0.tcp.ngrok.io:12345

# 3. 在其他机器上启动工作节点
python download/node_unified_complete.py --seeds "0.tcp.ngrok.io:12345" --ngrok --ngrok-auth-token YOUR_TOKEN
```

---

## 📊 性能参考

### 硬件要求

| 模型大小 | 最低内存 | 推荐内存 | GPU 显存 |
|---------|---------|---------|---------|
| 0.5B | 4GB | 8GB | 2GB+ |
| 1.5B | 8GB | 16GB | 4GB+ |
| 7B | 16GB | 32GB | 8GB+ |
| 14B | 32GB | 64GB | 16GB+ |

### 推理速度参考

| 硬件 | 模型 | 速度 (tokens/s) |
|------|------|----------------|
| RTX 4090 | 7B | ~80 |
| RTX 3080 | 7B | ~40 |
| CPU (8核) | 0.5B | ~10 |

---

## 📁 项目结构

```
servermodel/
├── download/
│   └── node_unified_complete.py   # 主程序（单文件，开箱即用）
├── ui/
│   └── index.html                 # Web UI 界面
├── scripts/
│   ├── start_cluster.sh           # 集群启动脚本
│   └── stop_cluster.sh            # 集群停止脚本
├── config.json                    # 配置文件（可选）
├── requirements.txt               # Python 依赖
├── Dockerfile                     # Docker 镜像配置
├── docker-compose.yml             # Docker Compose 配置
├── install.sh                     # Linux/Mac 安装脚本
├── install.bat                    # Windows 安装脚本
├── start.sh                       # 一键启动（Linux/Mac）
├── start.bat                      # 一键启动（Windows）
├── stop.sh                        # 停止服务（Linux/Mac）
├── stop.bat                       # 停止服务（Windows）
└── README.md                      # 本文档
```

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

---

## 📄 许可证

MIT License

---

## 🙏 致谢

- [HuggingFace Transformers](https://huggingface.co/transformers/)
- [Qwen Team](https://github.com/QwenLM/Qwen)
- [PyTorch](https://pytorch.org/)
