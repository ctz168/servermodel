# 统一分布式推理系统启动流程详解

## 一、启动流程概览

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           启动流程总览                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐                                                            │
│  │   main()     │  1. 解析命令行参数                                          │
│  └──────┬───────┘                                                            │
│         │                                                                    │
│         ▼                                                                    │
│  ┌──────────────┐                                                            │
│  │ 创建配置     │  2. 创建 UnifiedConfig                                      │
│  │ UnifiedConfig│                                                            │
│  └──────┬───────┘                                                            │
│         │                                                                    │
│         ▼                                                                    │
│  ┌──────────────┐                                                            │
│  │ 自动模式选择 │  3. 如果 --auto，自动选择最佳模式                            │
│  │ (可选)       │                                                            │
│  └──────┬───────┘                                                            │
│         │                                                                    │
│         ▼                                                                    │
│  ┌──────────────┐                                                            │
│  │ 创建节点     │  4. 创建 UnifiedNode 实例                                   │
│  │ UnifiedNode  │                                                            │
│  └──────┬───────┘                                                            │
│         │                                                                    │
│         ▼                                                                    │
│  ┌──────────────┐                                                            │
│  │ node.start() │  5. 启动节点                                                │
│  └──────┬───────┘                                                            │
│         │                                                                    │
│         ▼                                                                    │
│  ┌──────────────┐                                                            │
│  │ 主循环等待   │  6. 进入主循环，等待请求                                     │
│  └──────────────┘                                                            │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 二、详细启动流程

### 阶段 1: 命令行参数解析

```python
# main() 函数
def main():
    parser = argparse.ArgumentParser(description="统一分布式推理系统")
    
    # 基础配置
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--api-port", type=int, default=8080)
    parser.add_argument("--model", type=str, default="Qwen/Qwen2.5-0.5B-Instruct")
    parser.add_argument("--seeds", type=str, default="")
    
    # 模式选择
    parser.add_argument("--mode", default="data_parallel")
    parser.add_argument("--schedule", default="raft")
    
    # ...
    
    args = parser.parse_args()
```

**支持的参数：**

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--port` | 5000 | 节点通信端口 |
| `--api-port` | 8080 | API 服务端口 |
| `--model` | Qwen/Qwen2.5-0.5B-Instruct | 模型名称 |
| `--seeds` | "" | 种子节点列表 |
| `--mode` | data_parallel | 并行模式 |
| `--schedule` | raft | 调度模式 |
| `--auto` | False | 自动模式选择 |

---

### 阶段 2: 创建配置对象

```python
# 创建配置
config = UnifiedConfig(
    port=args.port,
    api_port=args.api_port,
    model_name=args.model,
    seeds=args.seeds.split(",") if args.seeds else [],
    parallel_mode=args.mode,
    schedule_mode=args.schedule,
    # ...
)
```

**配置初始化流程：**

```
UnifiedConfig.__post_init__()
    │
    ├── 生成 node_id (UUID)
    ├── 生成 node_name (Node-{id[:8]})
    ├── 转换 parallel_mode 为枚举
    └── 转换 schedule_mode 为枚举
```

---

### 阶段 3: 自动模式选择（可选）

```python
if args.auto:
    print("[自动模式] 检测系统资源...")
    info = ResourceMonitor.get_system_info()
    
    mode = ModeSelector.auto_select(
        num_nodes=1,
        total_memory_gb=info["memory_total_gb"],
        model_size_gb=2.0,
        bandwidth_mbps=1000
    )
    
    config.parallel_mode = mode
```

**自动选择逻辑：**

```
┌─────────────────────────────────────────────────────────────────┐
│                    自动模式选择决策树                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  单节点?                                                         │
│     │                                                            │
│     ├── 是 ──▶ 数据并行 (data_parallel)                          │
│     │                                                            │
│     └── 否 ──▶ 每节点内存足够加载完整模型?                        │
│                    │                                             │
│                    ├── 是 ──▶ 数据并行 (data_parallel)            │
│                    │                                             │
│                    └── 否 ──▶ 网络带宽?                           │
│                                    │                             │
│                                    ├── ≥10Gbps ──▶ Tensor并行     │
│                                    ├── ≥1Gbps  ──▶ Pipeline并行   │
│                                    └── <1Gbps  ──▶ 混合并行       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

### 阶段 4: 创建节点实例

```python
node = UnifiedNode(config)
```

**UnifiedNode.__init__() 初始化流程：**

```
UnifiedNode.__init__(config)
    │
    ├── 创建 NetworkManager(config)     # 网络管理器
    ├── 创建 RaftElection(config)       # Raft 选举
    ├── 创建 ModelManager(config)       # 模型管理器
    ├── 创建 LoadBalancer(config)       # 负载均衡器
    │
    ├── 创建 NodeInfo                   # 节点信息
    │   ├── node_id
    │   ├── node_name
    │   ├── host (获取本机IP)
    │   └── port
    │
    ├── 初始化任务队列
    │   ├── pending_tasks = deque()
    │   ├── running_tasks = {}
    │   └── completed_tasks = {}
    │
    └── 初始化状态
        ├── running = False
        ├── api_server = None
        └── start_time = time.time()
```

---

### 阶段 5: 启动节点 (node.start())

```python
node.start()
```

**详细启动流程：**

```
UnifiedNode.start()
    │
    ├── 1. 打印启动横幅 (_print_banner)
    │
    ├── 2. 设置运行状态
    │       running = True
    │
    ├── 3. 更新资源信息 (_update_resource_info)
    │       ├── 获取内存信息
    │       ├── 获取 CPU 信息
    │       └── 获取 GPU 信息
    │
    ├── 4. 启动网络服务 (network.start_server)
    │       ├── 创建 TCP Socket
    │       ├── 绑定端口
    │       ├── 开始监听
    │       └── 启动接受连接线程
    │
    ├── 5. 启动选举服务 (election.start) [如果调度模式是 Raft]
    │       ├── 注册消息处理器
    │       └── 启动选举定时器
    │
    ├── 6. 注册消息处理器 (_register_handlers)
    │       ├── DISCOVER
    │       ├── INFERENCE_REQUEST
    │       ├── TASK_ASSIGN
    │       └── PIPELINE_DATA
    │
    ├── 7. 加载模型 (model_manager.load)
    │       ├── 加载 Tokenizer
    │       ├── 加载模型权重
    │       ├── 移动到设备 (CPU/GPU)
    │       └── 设置为评估模式
    │
    ├── 8. 启动 API 服务器 (_start_api_server)
    │       ├── 创建 HTTPServer
    │       └── 启动服务线程
    │
    ├── 9. 启动后台任务
    │       ├── 心跳循环线程 (_heartbeat_loop)
    │       └── 任务处理线程 (_task_loop)
    │
    └── 10. 进入主循环
            while running:
                time.sleep(1)
```

---

## 三、各组件启动详解

### 3.1 网络管理器启动

```python
# NetworkManager.start_server()
def start_server(self):
    # 1. 创建 TCP Socket
    self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    
    # 2. 设置选项
    self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    # 3. 绑定地址
    self.server_socket.bind((self.config.host, self.config.port))
    
    # 4. 开始监听
    self.server_socket.listen(20)
    self.server_socket.settimeout(1.0)
    
    # 5. 设置运行状态
    self.running = True
    
    # 6. 启动接受连接线程
    threading.Thread(target=self._accept_loop, daemon=True).start()
```

**网络架构：**

```
┌─────────────────────────────────────────────────────────────────┐
│                        网络架构                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────┐                                            │
│  │  TCP Server     │  监听 0.0.0.0:5000                          │
│  │  (主线程)       │                                            │
│  └────────┬────────┘                                            │
│           │                                                      │
│           ▼                                                      │
│  ┌─────────────────┐                                            │
│  │  Accept Loop    │  接受新连接                                 │
│  │  (守护线程)     │                                            │
│  └────────┬────────┘                                            │
│           │                                                      │
│           ▼                                                      │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │ Connection 1    │  │ Connection 2    │  │ Connection N    │ │
│  │ (守护线程)      │  │ (守护线程)      │  │ (守护线程)      │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 Raft 选举启动

```python
# RaftElection.start()
def start(self):
    self.running = True
    
    # 1. 注册消息处理器
    self.network.register_handler(MessageType.REQUEST_VOTE, self._handle_vote_request)
    self.network.register_handler(MessageType.HEARTBEAT, self._handle_heartbeat)
    
    # 2. 启动选举定时器
    self._reset_election_timer()
```

**选举流程：**

```
┌─────────────────────────────────────────────────────────────────┐
│                      Raft 选举流程                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  初始状态: FOLLOWER                                              │
│       │                                                          │
│       ▼                                                          │
│  ┌─────────────────┐                                            │
│  │ 选举定时器      │  随机超时 (3-6秒)                           │
│  │ 等待心跳        │                                            │
│  └────────┬────────┘                                            │
│           │                                                      │
│           ├── 收到心跳 ──▶ 重置定时器                            │
│           │                                                      │
│           └── 超时 ──▶ 开始选举                                  │
│                           │                                      │
│                           ▼                                      │
│                    ┌─────────────────┐                           │
│                    │ 成为 CANDIDATE  │                           │
│                    │ term++          │                           │
│                    │ 投票给自己      │                           │
│                    └────────┬────────┘                           │
│                             │                                    │
│                             ▼                                    │
│                    ┌─────────────────┐                           │
│                    │ 广播投票请求    │                           │
│                    │ REQUEST_VOTE    │                           │
│                    └────────┬────────┘                           │
│                             │                                    │
│                             ▼                                    │
│                    ┌─────────────────┐                           │
│                    │ 收集投票        │                           │
│                    └────────┬────────┘                           │
│                             │                                    │
│              ┌──────────────┼──────────────┐                     │
│              │              │              │                     │
│              ▼              ▼              ▼                     │
│        获得多数票      未获得多数票    收到更高任期               │
│              │              │              │                     │
│              ▼              ▼              ▼                     │
│        成为 LEADER    保持 CANDIDATE  成为 FOLLOWER              │
│        发送心跳        等待结果        更新 term                  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 3.3 模型加载

```python
# ModelManager.load()
def load(self, shard_info: Dict = None) -> bool:
    # 1. 加载 Tokenizer
    print("   [1/2] 加载Tokenizer...")
    self.tokenizer = AutoTokenizer.from_pretrained(
        self.config.model_name,
        trust_remote_code=True
    )
    
    # 2. 检测设备
    if torch.cuda.is_available():
        device = "cuda"
        torch_dtype = torch.float16
    else:
        device = "cpu"
        torch_dtype = torch.float32
    
    # 3. 加载模型
    print("   [2/2] 加载模型权重...")
    self.model = AutoModelForCausalLM.from_pretrained(
        self.config.model_name,
        torch_dtype=torch_dtype,
        trust_remote_code=True,
        low_cpu_mem_usage=True,
    )
    
    # 4. 移动到设备
    if device != "cpu":
        self.model = self.model.to(device)
    
    # 5. 设置评估模式
    self.model.eval()
```

**模型加载流程：**

```
┌─────────────────────────────────────────────────────────────────┐
│                      模型加载流程                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. 加载 Tokenizer                                               │
│     │                                                            │
│     ├── 从 HuggingFace 下载/加载                                 │
│     ├── 设置 pad_token = eos_token                               │
│     │                                                            │
│     ▼                                                            │
│  2. 检测设备                                                      │
│     │                                                            │
│     ├── CUDA 可用? ──▶ device="cuda", dtype=float16             │
│     ├── MPS 可用?  ──▶ device="mps", dtype=float16              │
│     └── 否则       ──▶ device="cpu", dtype=float32              │
│     │                                                            │
│     ▼                                                            │
│  3. 加载模型权重                                                  │
│     │                                                            │
│     ├── 从 HuggingFace 下载/加载                                 │
│     ├── low_cpu_mem_usage=True (减少内存峰值)                    │
│     │                                                            │
│     ▼                                                            │
│  4. 移动到设备                                                    │
│     │                                                            │
│     └── model.to(device)                                         │
│     │                                                            │
│     ▼                                                            │
│  5. 设置评估模式                                                  │
│     │                                                            │
│     └── model.eval()                                             │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 3.4 API 服务器启动

```python
# UnifiedNode._start_api_server()
def _start_api_server(self):
    # 1. 设置节点引用
    APIRequestHandler.node = self
    
    # 2. 创建 HTTP 服务器
    self.api_server = HTTPServer(
        (self.config.api_host, self.config.api_port),
        APIRequestHandler
    )
    
    # 3. 启动服务线程
    threading.Thread(target=self.api_server.serve_forever, daemon=True).start()
```

**API 端点处理：**

```
┌─────────────────────────────────────────────────────────────────┐
│                      API 请求处理                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  HTTP Request                                                    │
│       │                                                          │
│       ▼                                                          │
│  ┌─────────────────┐                                            │
│  │ APIRequestHandler│                                           │
│  └────────┬────────┘                                            │
│           │                                                      │
│           ├── GET /              ──▶ 服务信息                    │
│           ├── GET /health        ──▶ 健康检查                    │
│           ├── GET /status        ──▶ 完整状态                    │
│           ├── GET /nodes         ──▶ 节点列表                    │
│           ├── GET /models        ──▶ 模型列表                    │
│           ├── GET /stats         ──▶ 统计信息                    │
│           │                                                      │
│           ├── POST /v1/chat/completions                         │
│           │       │                                              │
│           │       ├── 解析 OpenAI 格式请求                       │
│           │       ├── 构建 prompt                               │
│           │       ├── 调用 model_manager.inference()            │
│           │       └── 返回 OpenAI 格式响应                       │
│           │                                                      │
│           ├── POST /v1/completions                              │
│           │       │                                              │
│           │       ├── 解析请求                                   │
│           │       ├── 调用推理                                   │
│           │       └── 返回响应                                   │
│           │                                                      │
│           └── POST /inference                                    │
│                   │                                              │
│                   ├── 解析原生请求                               │
│                   ├── 调用推理                                   │
│                   └── 返回响应                                   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 四、后台任务

### 4.1 心跳循环

```python
def _heartbeat_loop(self):
    while self.running:
        # 更新资源信息
        self._update_resource_info()
        
        # 等待
        time.sleep(self.config.health_check_interval)  # 默认 5 秒
```

### 4.2 任务处理循环

```python
def _task_loop(self):
    while self.running:
        with self.task_lock:
            while self.pending_tasks:
                task = self.pending_tasks.popleft()
                
                # 启动新线程处理任务
                threading.Thread(
                    target=self._process_task,
                    args=(task,),
                    daemon=True
                ).start()
        
        time.sleep(0.1)
```

---

## 五、完整启动时序图

```
┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐
│  main   │     │ Unified │     │ Network │     │  Raft   │     │  Model  │
│         │     │  Node   │     │ Manager │     │ Election│     │ Manager │
└────┬────┘     └────┬────┘     └────┬────┘     └────┬────┘     └────┬────┘
     │               │               │               │               │
     │ 解析参数       │               │               │               │
     │──────────────▶│               │               │               │
     │               │               │               │               │
     │ 创建配置       │               │               │               │
     │──────────────▶│               │               │               │
     │               │               │               │               │
     │               │ __init__      │               │               │
     │               │──────────────▶│               │               │
     │               │               │               │               │
     │               │               │ __init__      │               │
     │               │               │──────────────▶│               │
     │               │               │               │               │
     │               │               │               │ __init__      │
     │               │               │               │──────────────▶│
     │               │               │               │               │
     │ node.start()  │               │               │               │
     │──────────────▶│               │               │               │
     │               │               │               │               │
     │               │ start_server  │               │               │
     │               │──────────────▶│               │               │
     │               │               │               │               │
     │               │               │ ◀─────────────│               │
     │               │               │  监听端口     │               │
     │               │               │               │               │
     │               │ start         │               │               │
     │               │───────────────────────────────▶               │
     │               │               │               │               │
     │               │               │               │ 启动定时器    │
     │               │               │               │               │
     │               │ load          │               │               │
     │               │───────────────────────────────────────────────▶
     │               │               │               │               │
     │               │               │               │               │ 加载模型
     │               │               │               │               │
     │               │ _start_api_server             │               │
     │               │──────────────▶│               │               │
     │               │               │               │               │
     │               │               │ 启动 HTTP 服务│               │
     │               │               │               │               │
     │               │ 启动后台线程   │               │               │
     │               │               │               │               │
     │               │ 进入主循环     │               │               │
     │               │               │               │               │
     │               │ ◀─────────────│               │               │
     │               │  等待请求     │               │               │
     │               │               │               │               │
     ▼               ▼               ▼               ▼               ▼
```

---

## 六、启动命令示例

### 6.1 单节点启动

```bash
# 最简单启动（使用默认配置）
python node_unified_complete.py

# 指定模型
python node_unified_complete.py --model "Qwen/Qwen2.5-1.5B-Instruct"

# 自动模式选择
python node_unified_complete.py --auto

# 指定端口
python node_unified_complete.py --port 6000 --api-port 9000
```

### 6.2 多节点集群启动

```bash
# 节点 1 (领导节点)
python node_unified_complete.py \
    --port 5000 \
    --api-port 8080 \
    --node-name "leader"

# 节点 2 (工作节点)
python node_unified_complete.py \
    --port 5001 \
    --api-port 8081 \
    --seeds "192.168.1.1:5000" \
    --node-name "worker-1"

# 节点 3 (工作节点)
python node_unified_complete.py \
    --port 5002 \
    --api-port 8082 \
    --seeds "192.168.1.1:5000" \
    --node-name "worker-2"
```

### 6.3 Pipeline 并行启动

```bash
# 4 阶段 Pipeline
python node_unified_complete.py \
    --mode pipeline_parallel \
    --stages 4 \
    --model "Qwen/Qwen2.5-7B-Instruct"
```

### 6.4 混合并行启动

```bash
# 2 数据并行 × 2 Tensor 并行 × 2 Pipeline 并行
python node_unified_complete.py \
    --mode hybrid \
    --dp 2 --tp 2 --pp 2
```

---

## 七、启动后验证

### 7.1 健康检查

```bash
curl http://localhost:8080/health
```

响应：
```json
{
  "status": "healthy",
  "health_score": 85.5,
  "model_loaded": true,
  "timestamp": 1710000000.0
}
```

### 7.2 状态检查

```bash
curl http://localhost:8080/status
```

### 7.3 测试推理

```bash
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen/Qwen2.5-0.5B-Instruct",
    "messages": [
      {"role": "user", "content": "你好"}
    ]
  }'
```

---

## 八、常见启动问题

### 8.1 端口被占用

```
错误: [Errno 98] Address already in use

解决: 更换端口
python node_unified_complete.py --port 6000 --api-port 9000
```

### 8.2 内存不足

```
错误: CUDA out of memory

解决: 使用更小的模型或 CPU 模式
python node_unified_complete.py --model "Qwen/Qwen2.5-0.5B-Instruct"
```

### 8.3 模型下载失败

```
错误: ConnectionError

解决: 使用镜像
export HF_ENDPOINT=https://hf-mirror.com
python node_unified_complete.py
```
