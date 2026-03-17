#!/usr/bin/env python3
"""
分布式大模型推理系统 - 统一去中心化版本
==========================================

核心特性:
1. 自动节点发现 - 启动时自动检测其他节点
2. 自动角色选举 - 第一个节点自动成为领导节点
3. 分布式选举 - 使用Raft协议进行领导选举
4. 统一API入口 - 领导节点提供统一API服务
5. 联合分布式推理 - 支持模型分片和Pipeline并行
6. 故障自动恢复 - 领导节点故障时自动重新选举

工作流程:
1. 节点启动，检查是否有其他节点存在
2. 如果没有其他节点 -> 自动成为领导节点（同时也是工作节点）
3. 如果有其他节点 -> 加入集群，参与选举
4. 领导节点负责：资源分配、API统一入口、任务调度
5. 所有节点都可以参与推理计算

使用方法:
    # 第一个节点（自动成为领导）
    python node_unified.py --port 5000

    # 后续节点（自动发现并加入）
    python node_unified.py --port 5001 --seeds "localhost:5000"
"""

import os

# HuggingFace 镜像配置（国内网络优化）
os.environ['HF_ENDPOINT'] = os.environ.get('HF_ENDPOINT', 'https://hf-mirror.com')
os.environ['HF_HOME'] = os.environ.get('HF_HOME', os.path.expanduser('~/.cache/huggingface'))

import sys
import time
import json
import uuid
import socket
import threading
import hashlib
import random
import pickle
import zlib
import asyncio
from typing import Dict, List, Optional, Any, Set, Tuple, Callable
from dataclasses import dataclass, field
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor, Future
from enum import Enum
import struct
from datetime import datetime
from pathlib import Path

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False
    print("警告: psutil未安装，请运行: pip install psutil")

try:
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, AutoConfig
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False
    print("警告: torch/transformers未安装，请运行: pip install torch transformers")

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


# ==================== 枚举定义 ====================

class NodeRole(Enum):
    """节点角色"""
    LEADER = "leader"           # 领导节点：资源分配、API入口、任务调度
    WORKER = "worker"           # 工作节点：参与推理计算
    CANDIDATE = "candidate"     # 候选节点：参与选举
    FOLLOWER = "follower"       # 跟随节点：等待指令


class NodeState(Enum):
    """节点状态"""
    INITIALIZING = "initializing"   # 初始化中
    DISCOVERING = "discovering"     # 发现节点中
    ELECTING = "electing"           # 选举中
    READY = "ready"                 # 就绪
    RUNNING = "running"             # 运行中
    STOPPING = "stopping"           # 停止中
    ERROR = "error"                 # 错误


class MessageType(Enum):
    """消息类型"""
    # 节点发现
    DISCOVER = "discover"
    DISCOVER_RESPONSE = "discover_response"
    NODE_JOIN = "node_join"
    NODE_LEAVE = "node_leave"
    
    # 心跳
    HEARTBEAT = "heartbeat"
    HEARTBEAT_RESPONSE = "heartbeat_response"
    
    # 选举 (Raft)
    REQUEST_VOTE = "request_vote"
    VOTE_RESPONSE = "vote_response"
    
    # 状态同步
    STATE_SYNC = "state_sync"
    STATE_SYNC_ACK = "state_sync_ack"
    
    # 任务
    TASK_ASSIGN = "task_assign"
    TASK_RESULT = "task_result"
    TASK_FORWARD = "task_forward"
    
    # 资源
    RESOURCE_REPORT = "resource_report"
    RESOURCE_REQUEST = "resource_request"
    
    # 推理
    INFERENCE_REQUEST = "inference_request"
    INFERENCE_RESPONSE = "inference_response"
    
    # Pipeline
    PIPELINE_INIT = "pipeline_init"
    PIPELINE_DATA = "pipeline_data"
    PIPELINE_RESULT = "pipeline_result"


# ==================== 配置 ====================

@dataclass
class UnifiedConfig:
    """统一配置"""
    # 节点配置
    node_id: str = ""
    node_name: str = ""
    host: str = "0.0.0.0"
    port: int = 5000
    
    # 模型配置
    model_name: str = "Qwen/Qwen2.5-0.5B-Instruct"
    model_memory_gb: float = 2.0
    max_workers: int = 2
    
    # 集群配置
    seeds: List[str] = field(default_factory=list)
    discovery_port: int = 9000
    heartbeat_interval: float = 2.0
    election_timeout_min: float = 3.0
    election_timeout_max: float = 6.0
    leader_timeout: float = 10.0
    
    # 资源配置
    min_memory_gb: float = 2.0
    min_cpu_percent: float = 10.0
    
    # 推理配置
    enable_pipeline: bool = False
    pipeline_stages: int = 1
    
    # API配置
    api_port: int = 8080
    
    def __post_init__(self):
        if not self.node_id:
            self.node_id = str(uuid.uuid4())
        if not self.node_name:
            self.node_name = f"Node-{self.node_id[:8]}"


# ==================== 数据结构 ====================

@dataclass
class NodeInfo:
    """节点信息"""
    node_id: str
    node_name: str
    host: str
    port: int
    role: NodeRole = NodeRole.FOLLOWER
    state: NodeState = NodeState.INITIALIZING
    
    # 资源信息
    memory_total_gb: float = 0.0
    memory_available_gb: float = 0.0
    cpu_percent: float = 0.0
    cpu_cores: int = 0
    gpu_available: bool = False
    gpu_memory_gb: float = 0.0
    
    # 模型信息
    model_loaded: bool = False
    model_name: str = ""
    model_shard_id: int = -1  # -1表示完整模型
    
    # 状态
    last_heartbeat: float = 0.0
    is_alive: bool = True
    active_tasks: int = 0
    max_workers: int = 2
    
    # 选举相关
    term: int = 0
    
    def to_dict(self) -> Dict:
        return {
            "node_id": self.node_id,
            "node_name": self.node_name,
            "host": self.host,
            "port": self.port,
            "role": self.role.value,
            "state": self.state.value,
            "memory_total_gb": self.memory_total_gb,
            "memory_available_gb": self.memory_available_gb,
            "cpu_percent": self.cpu_percent,
            "cpu_cores": self.cpu_cores,
            "gpu_available": self.gpu_available,
            "gpu_memory_gb": self.gpu_memory_gb,
            "model_loaded": self.model_loaded,
            "model_name": self.model_name,
            "model_shard_id": self.model_shard_id,
            "last_heartbeat": self.last_heartbeat,
            "is_alive": self.is_alive,
            "active_tasks": self.active_tasks,
            "max_workers": self.max_workers,
            "term": self.term,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'NodeInfo':
        return cls(
            node_id=data.get("node_id", ""),
            node_name=data.get("node_name", ""),
            host=data.get("host", ""),
            port=data.get("port", 0),
            role=NodeRole(data.get("role", "follower")),
            state=NodeState(data.get("state", "initializing")),
            memory_total_gb=data.get("memory_total_gb", 0.0),
            memory_available_gb=data.get("memory_available_gb", 0.0),
            cpu_percent=data.get("cpu_percent", 0.0),
            cpu_cores=data.get("cpu_cores", 0),
            gpu_available=data.get("gpu_available", False),
            gpu_memory_gb=data.get("gpu_memory_gb", 0.0),
            model_loaded=data.get("model_loaded", False),
            model_name=data.get("model_name", ""),
            model_shard_id=data.get("model_shard_id", -1),
            last_heartbeat=data.get("last_heartbeat", 0.0),
            is_alive=data.get("is_alive", True),
            active_tasks=data.get("active_tasks", 0),
            max_workers=data.get("max_workers", 2),
            term=data.get("term", 0),
        )


@dataclass
class TaskInfo:
    """任务信息"""
    task_id: str
    prompt: str
    status: str  # pending, running, completed, failed
    assigned_node: Optional[str] = None
    result: Optional[str] = None
    created_at: float = 0.0
    started_at: float = 0.0
    completed_at: float = 0.0
    latency: float = 0.0
    tokens: int = 0
    error: Optional[str] = None
    params: Dict = field(default_factory=dict)


# ==================== 资源监控 ====================

class ResourceMonitor:
    """资源监控器"""
    
    @staticmethod
    def get_system_info() -> Dict:
        """获取系统信息"""
        info = {
            "memory_total_gb": 8.0,
            "memory_available_gb": 4.0,
            "cpu_percent": 50.0,
            "cpu_cores": 4,
            "gpu_available": False,
            "gpu_memory_gb": 0.0,
        }
        
        if HAS_PSUTIL:
            mem = psutil.virtual_memory()
            info["memory_total_gb"] = mem.total / (1024**3)
            info["memory_available_gb"] = mem.available / (1024**3)
            info["cpu_percent"] = psutil.cpu_percent(interval=0.1)
            info["cpu_cores"] = psutil.cpu_count() or 4
        
        if HAS_TORCH and torch.cuda.is_available():
            info["gpu_available"] = True
            info["gpu_memory_gb"] = torch.cuda.get_device_properties(0).total_memory / (1024**3)
        
        return info
    
    @staticmethod
    def can_run_model(model_memory_gb: float, min_memory_gb: float = 2.0) -> Tuple[bool, str]:
        """检查是否能运行模型"""
        info = ResourceMonitor.get_system_info()
        
        if info["memory_available_gb"] < min_memory_gb:
            return False, f"内存不足: {info['memory_available_gb']:.1f}GB < {min_memory_gb}GB"
        
        if info["memory_available_gb"] < model_memory_gb * 1.5:
            return False, f"内存不足以加载模型: 需要{model_memory_gb * 1.5:.1f}GB"
        
        return True, "资源充足"
    
    @staticmethod
    def get_resource_score() -> float:
        """获取资源评分 (0-100)"""
        info = ResourceMonitor.get_system_info()
        
        # 内存评分 (权重60%)
        mem_score = min(60, info["memory_available_gb"] * 6)
        
        # CPU评分 (权重30%)
        cpu_idle = 100 - info["cpu_percent"]
        cpu_score = min(30, cpu_idle * 0.3)
        
        # GPU评分 (权重10%)
        gpu_score = 10 if info["gpu_available"] else 0
        
        return mem_score + cpu_score + gpu_score


# ==================== 网络通信 ====================

class NetworkManager:
    """网络管理器 - 处理节点间通信"""
    
    def __init__(self, config: UnifiedConfig):
        self.config = config
        self.node_id = config.node_id
        
        # 连接管理
        self.connections: Dict[str, socket.socket] = {}
        self.known_nodes: Dict[str, NodeInfo] = {}
        
        # 消息处理器
        self.message_handlers: Dict[MessageType, Callable] = {}
        
        # 服务器socket
        self.server_socket: Optional[socket.socket] = None
        self.running = False
        
        # 锁
        self.lock = threading.Lock()
        
        # 回调
        self.on_message_received: Optional[Callable] = None
    
    def register_handler(self, msg_type: MessageType, handler: Callable):
        """注册消息处理器"""
        self.message_handlers[msg_type] = handler
    
    def start_server(self):
        """启动TCP服务器"""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.config.host, self.config.port))
        self.server_socket.listen(20)
        self.server_socket.settimeout(1.0)
        
        self.running = True
        
        # 启动接受连接线程
        threading.Thread(target=self._accept_loop, daemon=True).start()
        
        print(f"[网络] TCP服务器启动: {self.config.host}:{self.config.port}")
    
    def _accept_loop(self):
        """接受连接循环"""
        while self.running:
            try:
                conn, addr = self.server_socket.accept()
                threading.Thread(target=self._handle_connection, args=(conn, addr), daemon=True).start()
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    print(f"[网络] 接受连接错误: {e}")
    
    def _handle_connection(self, conn: socket.socket, addr):
        """处理连接"""
        try:
            # 接收数据
            data = b""
            while True:
                chunk = conn.recv(65536)
                if not chunk:
                    break
                data += chunk
            
            if data:
                # 解析消息
                message = self._decode_message(data)
                if message:
                    msg_type = MessageType(message.get("type"))
                    msg_data = message.get("data", {})
                    from_node = message.get("from_node", "")
                    
                    # 调用处理器
                    if msg_type in self.message_handlers:
                        handler = self.message_handlers[msg_type]
                        response = handler(msg_data, from_node)
                        
                        # 发送响应
                        if response:
                            response_msg = {
                                "type": msg_type.value + "_response",
                                "data": response,
                                "from_node": self.node_id,
                            }
                            conn.sendall(self._encode_message(response_msg))
        except Exception as e:
            pass
        finally:
            conn.close()
    
    def connect_to_node(self, host: str, port: int) -> bool:
        """连接到节点"""
        node_addr = f"{host}:{port}"
        
        if node_addr in self.connections:
            return True
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((host, port))
            self.connections[node_addr] = sock
            print(f"[网络] 已连接到节点: {node_addr}")
            return True
        except Exception as e:
            print(f"[网络] 连接失败 {node_addr}: {e}")
            return False
    
    def send_message(self, host: str, port: int, msg_type: MessageType, 
                     data: Dict, wait_response: bool = False, timeout: float = 10.0) -> Optional[Dict]:
        """发送消息到节点"""
        node_addr = f"{host}:{port}"
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            sock.connect((host, port))
            
            # 发送消息
            message = {
                "type": msg_type.value,
                "data": data,
                "from_node": self.node_id,
                "timestamp": time.time(),
            }
            sock.sendall(self._encode_message(message))
            
            if wait_response:
                # 等待响应
                sock.shutdown(socket.SHUT_WR)
                response_data = b""
                while True:
                    chunk = sock.recv(65536)
                    if not chunk:
                        break
                    response_data += chunk
                
                if response_data:
                    response = self._decode_message(response_data)
                    return response
            
            sock.close()
            return None
            
        except Exception as e:
            print(f"[网络] 发送消息失败 {node_addr}: {e}")
            return None
    
    def broadcast(self, msg_type: MessageType, data: Dict, exclude_nodes: Set[str] = None):
        """广播消息到所有已知节点"""
        exclude_nodes = exclude_nodes or set()
        
        message = {
            "type": msg_type.value,
            "data": data,
            "from_node": self.node_id,
            "timestamp": time.time(),
        }
        
        for node_id, node_info in list(self.known_nodes.items()):
            if node_id in exclude_nodes or node_id == self.node_id:
                continue
            
            try:
                self.send_message(
                    node_info.host, node_info.port,
                    msg_type, data, wait_response=False
                )
            except:
                pass
    
    def _encode_message(self, message: Dict) -> bytes:
        """编码消息"""
        return zlib.compress(pickle.dumps(message))
    
    def _decode_message(self, data: bytes) -> Dict:
        """解码消息"""
        return pickle.loads(zlib.decompress(data))
    
    def stop(self):
        """停止网络"""
        self.running = False
        
        for sock in self.connections.values():
            try:
                sock.close()
            except:
                pass
        
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass


# ==================== 节点发现 ====================

class NodeDiscovery:
    """节点发现服务"""
    
    def __init__(self, config: UnifiedConfig, network: NetworkManager):
        self.config = config
        self.network = network
        self.node_id = config.node_id
        
        # 发现socket (UDP广播)
        self.discovery_socket: Optional[socket.socket] = None
        self.running = False
        
        # 已发现节点
        self.discovered_nodes: Dict[str, NodeInfo] = {}
    
    def start(self):
        """启动发现服务"""
        # UDP广播socket
        self.discovery_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.discovery_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.discovery_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.discovery_socket.bind(('0.0.0.0', self.config.discovery_port))
        self.discovery_socket.settimeout(1.0)
        
        self.running = True
        
        # 启动广播和监听线程
        threading.Thread(target=self._broadcast_loop, daemon=True).start()
        threading.Thread(target=self._listen_loop, daemon=True).start()
        
        print(f"[发现] 节点发现服务启动，端口: {self.config.discovery_port}")
    
    def _broadcast_loop(self):
        """广播本节点信息"""
        while self.running:
            try:
                message = json.dumps({
                    "type": "discovery",
                    "node_id": self.node_id,
                    "node_name": self.config.node_name,
                    "host": self._get_local_ip(),
                    "port": self.config.port,
                    "timestamp": time.time(),
                }).encode()
                
                self.discovery_socket.sendto(
                    message,
                    ('<broadcast>', self.config.discovery_port)
                )
            except:
                pass
            
            time.sleep(5)
    
    def _listen_loop(self):
        """监听其他节点广播"""
        while self.running:
            try:
                data, addr = self.discovery_socket.recvfrom(4096)
                message = json.loads(data.decode())
                
                if message.get("type") == "discovery":
                    node_id = message.get("node_id")
                    
                    if node_id and node_id != self.node_id:
                        node_info = NodeInfo(
                            node_id=node_id,
                            node_name=message.get("node_name", ""),
                            host=message.get("host", ""),
                            port=message.get("port", 0),
                            last_heartbeat=time.time(),
                        )
                        
                        self.discovered_nodes[node_id] = node_info
                        self.network.known_nodes[node_id] = node_info
                        
            except socket.timeout:
                continue
            except:
                pass
    
    def discover_nodes(self, timeout: float = 5.0) -> Dict[str, NodeInfo]:
        """主动发现节点"""
        # 连接种子节点
        for seed in self.config.seeds:
            try:
                host, port = seed.split(":")
                self.network.connect_to_node(host, int(port))
                
                # 发送发现请求
                response = self.network.send_message(
                    host, int(port),
                    MessageType.DISCOVER,
                    {"node_id": self.node_id},
                    wait_response=True
                )
                
                if response:
                    nodes_data = response.get("data", {}).get("nodes", [])
                    for node_data in nodes_data:
                        node_info = NodeInfo.from_dict(node_data)
                        self.discovered_nodes[node_info.node_id] = node_info
                        self.network.known_nodes[node_info.node_id] = node_info
                        
            except Exception as e:
                print(f"[发现] 连接种子节点失败 {seed}: {e}")
        
        # 等待UDP广播发现
        time.sleep(timeout)
        
        return self.discovered_nodes
    
    def _get_local_ip(self) -> str:
        """获取本机IP"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"
    
    def stop(self):
        """停止发现服务"""
        self.running = False
        if self.discovery_socket:
            try:
                self.discovery_socket.close()
            except:
                pass


# ==================== Raft选举 ====================

class RaftElection:
    """Raft选举协议"""
    
    def __init__(self, config: UnifiedConfig, network: NetworkManager):
        self.config = config
        self.network = network
        self.node_id = config.node_id
        
        # 状态
        self.role = NodeRole.FOLLOWER
        self.current_term = 0
        self.voted_for: Optional[str] = None
        self.leader_id: Optional[str] = None
        
        # 选举相关
        self.last_heartbeat = time.time()
        self.election_timer: Optional[threading.Timer] = None
        self.votes_received: Set[str] = set()
        
        # 回调
        self.on_become_leader: Optional[Callable] = None
        self.on_become_follower: Optional[Callable] = None
        
        # 锁
        self.lock = threading.Lock()
        
        # 运行状态
        self.running = False
    
    def start(self):
        """启动选举服务"""
        self.running = True
        
        # 注册消息处理器
        self.network.register_handler(MessageType.REQUEST_VOTE, self._handle_vote_request)
        self.network.register_handler(MessageType.VOTE_RESPONSE, self._handle_vote_response)
        self.network.register_handler(MessageType.HEARTBEAT, self._handle_heartbeat)
        
        # 启动选举定时器
        self._reset_election_timer()
        
        print(f"[选举] Raft选举服务启动，初始角色: {self.role.value}")
    
    def _reset_election_timer(self):
        """重置选举定时器"""
        if self.election_timer:
            self.election_timer.cancel()
        
        # 随机超时时间
        timeout = random.uniform(
            self.config.election_timeout_min,
            self.config.election_timeout_max
        )
        
        self.election_timer = threading.Timer(timeout, self._start_election)
        self.election_timer.daemon = True
        self.election_timer.start()
    
    def _start_election(self):
        """开始选举"""
        if not self.running:
            return
        
        with self.lock:
            if self.role == NodeRole.LEADER:
                self._reset_election_timer()
                return
        
        print(f"[选举] 开始选举，任期 {self.current_term + 1}")
        
        with self.lock:
            self.role = NodeRole.CANDIDATE
            self.current_term += 1
            self.voted_for = self.node_id
            self.votes_received = {self.node_id}
        
        # 向所有节点请求投票
        vote_request = {
            "term": self.current_term,
            "candidate_id": self.node_id,
            "last_log_index": 0,
            "last_log_term": 0,
        }
        
        self.network.broadcast(MessageType.REQUEST_VOTE, vote_request)
        
        # 重置选举定时器
        self._reset_election_timer()
    
    def _handle_vote_request(self, data: Dict, from_node: str) -> Dict:
        """处理投票请求"""
        term = data.get("term", 0)
        candidate_id = data.get("candidate_id")
        
        response = {
            "term": self.current_term,
            "vote_granted": False,
            "voter_id": self.node_id,
        }
        
        with self.lock:
            # 如果请求的任期更高
            if term > self.current_term:
                self.current_term = term
                self.voted_for = None
                self.role = NodeRole.FOLLOWER
            
            # 判断是否投票
            if term < self.current_term:
                return response
            
            if self.voted_for is None or self.voted_for == candidate_id:
                self.voted_for = candidate_id
                response["vote_granted"] = True
                self.last_heartbeat = time.time()
                self._reset_election_timer()
                print(f"[选举] 投票给 {candidate_id}")
        
        return response
    
    def _handle_vote_response(self, data: Dict, from_node: str):
        """处理投票响应"""
        with self.lock:
            if self.role != NodeRole.CANDIDATE:
                return
            
            term = data.get("term", 0)
            vote_granted = data.get("vote_granted", False)
            voter_id = data.get("voter_id", "")
            
            if term > self.current_term:
                self.current_term = term
                self.role = NodeRole.FOLLOWER
                self.voted_for = None
                return
            
            if vote_granted:
                self.votes_received.add(voter_id)
                
                # 检查是否获得多数票
                total_nodes = len(self.network.known_nodes) + 1
                majority = total_nodes // 2 + 1
                
                if len(self.votes_received) >= majority:
                    self._become_leader()
    
    def _handle_heartbeat(self, data: Dict, from_node: str) -> Dict:
        """处理心跳"""
        term = data.get("term", 0)
        leader_id = data.get("leader_id")
        
        with self.lock:
            if term >= self.current_term:
                self.current_term = term
                self.role = NodeRole.FOLLOWER
                self.leader_id = leader_id
                self.last_heartbeat = time.time()
                self._reset_election_timer()
        
        return {
            "term": self.current_term,
            "node_id": self.node_id,
        }
    
    def _become_leader(self):
        """成为领导节点"""
        print(f"[选举] 成为领导节点! 任期 {self.current_term}")
        
        self.role = NodeRole.LEADER
        self.leader_id = self.node_id
        
        # 启动心跳线程
        threading.Thread(target=self._send_heartbeats, daemon=True).start()
        
        # 回调
        if self.on_become_leader:
            self.on_become_leader()
    
    def _send_heartbeats(self):
        """发送心跳"""
        while self.running and self.role == NodeRole.LEADER:
            heartbeat = {
                "term": self.current_term,
                "leader_id": self.node_id,
            }
            
            self.network.broadcast(MessageType.HEARTBEAT, heartbeat)
            time.sleep(self.config.heartbeat_interval)
    
    def is_leader(self) -> bool:
        """是否是领导节点"""
        return self.role == NodeRole.LEADER
    
    def get_leader(self) -> Optional[str]:
        """获取领导节点ID"""
        return self.leader_id
    
    def stop(self):
        """停止选举服务"""
        self.running = False
        if self.election_timer:
            self.election_timer.cancel()


# ==================== 模型管理 ====================

class ModelManager:
    """模型管理器"""
    
    def __init__(self, config: UnifiedConfig):
        self.config = config
        self.model = None
        self.tokenizer = None
        self.loaded = False
        self.load_time = 0.0
        self.model_size_gb = 0.0
        
        # 分片信息
        self.shard_id = -1
        self.shard_layers: List = []
        self.is_first_shard = False
        self.is_last_shard = False
    
    def load(self, shard_id: int = -1, layer_start: int = 0, layer_end: int = -1) -> bool:
        """加载模型"""
        if not HAS_TORCH:
            print("[模型] PyTorch未安装，无法加载模型")
            return False
        
        if self.loaded:
            return True
        
        start_time = time.time()
        
        try:
            print(f"[模型] 加载模型: {self.config.model_name}")
            
            # 加载tokenizer
            print("   [1/3] 加载Tokenizer...")
            for retry in range(3):
                try:
                    self.tokenizer = AutoTokenizer.from_pretrained(
                        self.config.model_name,
                        trust_remote_code=True
                    )
                    break
                except Exception as e:
                    if retry == 2:
                        raise
                    print(f"   Tokenizer加载失败，重试 {retry+1}/3...")
                    time.sleep(2)
            
            if self.tokenizer.pad_token is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token
            
            # 加载模型
            print("   [2/3] 加载模型权重...")
            
            # 检测设备
            if torch.cuda.is_available():
                device = "cuda"
                torch_dtype = torch.float16
            elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
                device = "mps"
                torch_dtype = torch.float16
            else:
                device = "cpu"
                torch_dtype = torch.float32
            
            for retry in range(3):
                try:
                    self.model = AutoModelForCausalLM.from_pretrained(
                        self.config.model_name,
                        torch_dtype=torch_dtype,
                        trust_remote_code=True,
                        low_cpu_mem_usage=True,
                    )
                    if device != "cpu":
                        self.model = self.model.to(device)
                    break
                except Exception as e:
                    if retry == 2:
                        raise
                    print(f"   模型加载失败，重试 {retry+1}/3...")
                    time.sleep(5)
            
            self.model.eval()
            
            # 计算模型大小
            param_count = sum(p.numel() for p in self.model.parameters())
            self.model_size_gb = param_count * 4 / (1024**3)
            
            self.loaded = True
            self.load_time = time.time() - start_time
            
            print(f"[模型] 加载完成!")
            print(f"   参数量: {param_count/1e9:.2f}B")
            print(f"   大小: {self.model_size_gb:.2f}GB")
            print(f"   设备: {device}")
            print(f"   时间: {self.load_time:.1f}s")
            
            return True
            
        except Exception as e:
            print(f"[模型] 加载失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def unload(self):
        """卸载模型"""
        if self.model:
            del self.model
            self.model = None
        if self.tokenizer:
            del self.tokenizer
            self.tokenizer = None
        
        self.loaded = False
        
        if HAS_TORCH and torch.cuda.is_available():
            torch.cuda.empty_cache()
        
        import gc
        gc.collect()
        
        print("[模型] 已卸载")
    
    def inference(self, prompt: str, max_tokens: int = 256, 
                  temperature: float = 0.7, **kwargs) -> Dict:
        """推理"""
        if not self.loaded:
            return {"success": False, "error": "模型未加载"}
        
        try:
            start_time = time.time()
            
            # 编码
            inputs = self.tokenizer(prompt, return_tensors="pt")
            if self.model.device.type != "cpu":
                inputs = {k: v.to(self.model.device) for k, v in inputs.items()}
            
            # 生成
            with torch.no_grad():
                outputs = self.model.generate(
                    inputs["input_ids"],
                    max_new_tokens=max_tokens,
                    temperature=temperature if temperature > 0 else 1.0,
                    do_sample=temperature > 0,
                    pad_token_id=self.tokenizer.pad_token_id,
                    eos_token_id=self.tokenizer.eos_token_id,
                )
            
            # 解码
            latency = time.time() - start_time
            new_tokens = outputs.shape[1] - inputs["input_ids"].shape[1]
            response = self.tokenizer.decode(
                outputs[0][inputs["input_ids"].shape[1]:],
                skip_special_tokens=True
            )
            
            return {
                "success": True,
                "response": response,
                "tokens": new_tokens,
                "latency": latency,
                "throughput": new_tokens / latency if latency > 0 else 0,
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}


# ==================== 任务调度 ====================

class TaskScheduler:
    """任务调度器"""
    
    def __init__(self, config: UnifiedConfig, network: NetworkManager):
        self.config = config
        self.network = network
        self.node_id = config.node_id
        
        # 任务队列
        self.pending_tasks: deque = deque()
        self.running_tasks: Dict[str, TaskInfo] = {}
        self.completed_tasks: Dict[str, TaskInfo] = {}
        
        # 锁
        self.lock = threading.Lock()
    
    def submit_task(self, prompt: str, params: Dict = None) -> str:
        """提交任务"""
        task_id = str(uuid.uuid4())
        
        task = TaskInfo(
            task_id=task_id,
            prompt=prompt,
            status="pending",
            created_at=time.time(),
            params=params or {},
        )
        
        with self.lock:
            self.pending_tasks.append(task)
        
        print(f"[任务] 提交任务 {task_id[:8]}")
        return task_id
    
    def get_next_task(self) -> Optional[TaskInfo]:
        """获取下一个任务"""
        with self.lock:
            if self.pending_tasks:
                task = self.pending_tasks.popleft()
                task.status = "running"
                task.started_at = time.time()
                self.running_tasks[task.task_id] = task
                return task
        return None
    
    def complete_task(self, task_id: str, result: str, tokens: int, latency: float):
        """完成任务"""
        with self.lock:
            if task_id in self.running_tasks:
                task = self.running_tasks.pop(task_id)
                task.status = "completed"
                task.result = result
                task.tokens = tokens
                task.latency = latency
                task.completed_at = time.time()
                self.completed_tasks[task_id] = task
                print(f"[任务] 完成 {task_id[:8]} ({latency:.2f}s)")
    
    def fail_task(self, task_id: str, error: str):
        """任务失败"""
        with self.lock:
            if task_id in self.running_tasks:
                task = self.running_tasks.pop(task_id)
                task.status = "failed"
                task.error = error
                task.completed_at = time.time()
                self.completed_tasks[task_id] = task
                print(f"[任务] 失败 {task_id[:8]}: {error}")
    
    def assign_task_to_node(self, task: TaskInfo, node_info: NodeInfo) -> bool:
        """分配任务到节点"""
        try:
            response = self.network.send_message(
                node_info.host, node_info.port,
                MessageType.TASK_ASSIGN,
                {
                    "task_id": task.task_id,
                    "prompt": task.prompt,
                    "params": task.params,
                },
                wait_response=True
            )
            
            if response and response.get("data", {}).get("accepted"):
                task.assigned_node = node_info.node_id
                return True
        except:
            pass
        
        return False


# ==================== 统一节点 ====================

class UnifiedNode:
    """统一去中心化节点"""
    
    def __init__(self, config: UnifiedConfig):
        self.config = config
        self.node_id = config.node_id
        
        # 组件
        self.network = NetworkManager(config)
        self.discovery = NodeDiscovery(config, self.network)
        self.election = RaftElection(config, self.network)
        self.model = ModelManager(config)
        self.scheduler = TaskScheduler(config, self.network)
        
        # 节点信息
        self.node_info = self._create_node_info()
        self.known_nodes: Dict[str, NodeInfo] = {}
        
        # 状态
        self.running = False
        self.state = NodeState.INITIALIZING
        
        # 统计
        self.stats = {
            "tasks_completed": 0,
            "tasks_failed": 0,
            "total_tokens": 0,
            "total_latency": 0.0,
        }
        
        # 注册回调
        self.election.on_become_leader = self._on_become_leader
        self.election.on_become_follower = self._on_become_follower
        
        # 注册消息处理器
        self._register_handlers()
    
    def _create_node_info(self) -> NodeInfo:
        """创建节点信息"""
        info = ResourceMonitor.get_system_info()
        return NodeInfo(
            node_id=self.node_id,
            node_name=self.config.node_name,
            host=self._get_local_ip(),
            port=self.config.port,
            role=NodeRole.FOLLOWER,
            state=NodeState.INITIALIZING,
            memory_total_gb=info["memory_total_gb"],
            memory_available_gb=info["memory_available_gb"],
            cpu_percent=info["cpu_percent"],
            cpu_cores=info["cpu_cores"],
            gpu_available=info["gpu_available"],
            gpu_memory_gb=info["gpu_memory_gb"],
            model_name=self.config.model_name,
            max_workers=self.config.max_workers,
        )
    
    def _get_local_ip(self) -> str:
        """获取本机IP"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"
    
    def _register_handlers(self):
        """注册消息处理器"""
        self.network.register_handler(MessageType.DISCOVER, self._handle_discover)
        self.network.register_handler(MessageType.NODE_JOIN, self._handle_node_join)
        self.network.register_handler(MessageType.TASK_ASSIGN, self._handle_task_assign)
        self.network.register_handler(MessageType.INFERENCE_REQUEST, self._handle_inference_request)
        self.network.register_handler(MessageType.RESOURCE_REQUEST, self._handle_resource_request)
    
    def _handle_discover(self, data: Dict, from_node: str) -> Dict:
        """处理发现请求"""
        nodes_list = [self.node_info.to_dict()]
        for node_id, node_info in self.known_nodes.items():
            nodes_list.append(node_info.to_dict())
        
        return {"nodes": nodes_list}
    
    def _handle_node_join(self, data: Dict, from_node: str) -> Dict:
        """处理节点加入"""
        node_info = NodeInfo.from_dict(data)
        self.known_nodes[node_info.node_id] = node_info
        self.network.known_nodes[node_info.node_id] = node_info
        print(f"[节点] 新节点加入: {node_info.node_name}")
        return {"accepted": True}
    
    def _handle_task_assign(self, data: Dict, from_node: str) -> Dict:
        """处理任务分配"""
        if not self.model.loaded:
            return {"accepted": False, "reason": "模型未加载"}
        
        if self.node_info.active_tasks >= self.config.max_workers:
            return {"accepted": False, "reason": "节点繁忙"}
        
        # 异步执行任务
        task_id = data.get("task_id")
        prompt = data.get("prompt")
        params = data.get("params", {})
        
        threading.Thread(
            target=self._execute_task,
            args=(task_id, prompt, params, from_node),
            daemon=True
        ).start()
        
        return {"accepted": True}
    
    def _handle_inference_request(self, data: Dict, from_node: str) -> Dict:
        """处理推理请求"""
        prompt = data.get("prompt", "")
        params = data.get("params", {})
        
        if not self.model.loaded:
            return {"success": False, "error": "模型未加载"}
        
        result = self.model.inference(
            prompt,
            max_tokens=params.get("max_tokens", 256),
            temperature=params.get("temperature", 0.7),
        )
        
        return result
    
    def _handle_resource_request(self, data: Dict, from_node: str) -> Dict:
        """处理资源请求"""
        self._update_node_info()
        return self.node_info.to_dict()
    
    def _execute_task(self, task_id: str, prompt: str, params: Dict, from_node: str):
        """执行任务"""
        self.node_info.active_tasks += 1
        
        try:
            result = self.model.inference(
                prompt,
                max_tokens=params.get("max_tokens", 256),
                temperature=params.get("temperature", 0.7),
            )
            
            # 发送结果
            # 找到来源节点
            for node_id, node_info in self.known_nodes.items():
                if node_id == from_node:
                    self.network.send_message(
                        node_info.host, node_info.port,
                        MessageType.TASK_RESULT,
                        {
                            "task_id": task_id,
                            "result": result,
                        }
                    )
                    break
            
            if result.get("success"):
                self.stats["tasks_completed"] += 1
                self.stats["total_tokens"] += result.get("tokens", 0)
                self.stats["total_latency"] += result.get("latency", 0)
            else:
                self.stats["tasks_failed"] += 1
                
        except Exception as e:
            self.stats["tasks_failed"] += 1
            
        finally:
            self.node_info.active_tasks -= 1
    
    def _on_become_leader(self):
        """成为领导节点回调"""
        print(f"[领导] 成为集群领导节点")
        self.node_info.role = NodeRole.LEADER
        
        # 领导节点也需要加载模型
        if not self.model.loaded:
            self._load_model()
    
    def _on_become_follower(self):
        """成为跟随节点回调"""
        print(f"[跟随] 成为集群跟随节点")
        self.node_info.role = NodeRole.WORKER
        
        # 加载模型
        if not self.model.loaded:
            self._load_model()
    
    def _load_model(self):
        """加载模型"""
        can_run, reason = ResourceMonitor.can_run_model(
            self.config.model_memory_gb,
            self.config.min_memory_gb
        )
        
        if can_run:
            self.model.load()
            self.node_info.model_loaded = self.model.loaded
        else:
            print(f"[模型] 无法加载: {reason}")
    
    def _update_node_info(self):
        """更新节点信息"""
        info = ResourceMonitor.get_system_info()
        self.node_info.memory_available_gb = info["memory_available_gb"]
        self.node_info.cpu_percent = info["cpu_percent"]
        self.node_info.last_heartbeat = time.time()
    
    def start(self):
        """启动节点"""
        print(f"\n{'='*60}")
        print(f"  分布式大模型推理系统 - 统一去中心化节点")
        print(f"{'='*60}")
        print(f"  节点ID: {self.node_id}")
        print(f"  节点名称: {self.config.node_name}")
        print(f"  监听地址: {self.config.host}:{self.config.port}")
        print(f"  模型: {self.config.model_name}")
        print(f"{'='*60}\n")
        
        self.running = True
        self.state = NodeState.DISCOVERING
        
        # 启动网络服务
        self.network.start_server()
        
        # 启动发现服务
        self.discovery.start()
        
        # 发现其他节点
        print("[发现] 正在发现其他节点...")
        discovered = self.discovery.discover_nodes(timeout=5.0)
        
        if discovered:
            print(f"[发现] 发现 {len(discovered)} 个节点")
            self.known_nodes.update(discovered)
            self.network.known_nodes.update(discovered)
        else:
            print("[发现] 未发现其他节点，将成为第一个节点")
        
        # 启动选举服务
        self.election.start()
        
        # 如果没有其他节点，立即开始选举
        if not discovered:
            # 等待一小段时间确保选举定时器启动
            time.sleep(0.5)
            # 触发选举
            self.election._start_election()
        
        # 加载模型
        self._load_model()
        
        # 更新状态
        self.state = NodeState.RUNNING
        self.node_info.state = NodeState.RUNNING
        
        # 启动心跳和任务处理
        threading.Thread(target=self._heartbeat_loop, daemon=True).start()
        threading.Thread(target=self._task_loop, daemon=True).start()
        
        # 启动API服务（如果是领导节点）
        threading.Thread(target=self._api_server_loop, daemon=True).start()
        
        print(f"\n[节点] 启动完成，角色: {self.node_info.role.value}\n")
    
    def _heartbeat_loop(self):
        """心跳循环"""
        while self.running:
            self._update_node_info()
            time.sleep(self.config.heartbeat_interval)
    
    def _task_loop(self):
        """任务处理循环"""
        while self.running:
            try:
                # 如果是领导节点，分配任务
                if self.election.is_leader():
                    self._schedule_tasks()
                
                # 处理分配给自己的任务
                # (任务在 _handle_task_assign 中异步处理)
                
            except Exception as e:
                print(f"[任务] 错误: {e}")
            
            time.sleep(0.5)
    
    def _schedule_tasks(self):
        """调度任务（领导节点执行）"""
        task = self.scheduler.get_next_task()
        if not task:
            return
        
        # 找到可用节点
        available_nodes = self._get_available_nodes()
        if not available_nodes:
            # 没有可用节点，任务放回队列
            with self.scheduler.lock:
                self.scheduler.pending_tasks.appendleft(task)
            return
        
        # 选择负载最低的节点
        best_node = min(available_nodes, key=lambda n: n.active_tasks)
        
        # 分配任务
        if self.scheduler.assign_task_to_node(task, best_node):
            print(f"[调度] 分配任务 {task.task_id[:8]} 到 {best_node.node_name}")
        else:
            # 分配失败，放回队列
            with self.scheduler.lock:
                self.scheduler.pending_tasks.appendleft(task)
    
    def _get_available_nodes(self) -> List[NodeInfo]:
        """获取可用节点列表"""
        now = time.time()
        available = []
        
        # 检查自己
        if self.model.loaded and self.node_info.active_tasks < self.config.max_workers:
            available.append(self.node_info)
        
        # 检查其他节点
        for node_id, node_info in self.known_nodes.items():
            if (node_info.model_loaded and 
                node_info.is_alive and 
                now - node_info.last_heartbeat < 30 and
                node_info.active_tasks < node_info.max_workers):
                available.append(node_info)
        
        return available
    
    def _api_server_loop(self):
        """API服务循环"""
        from http.server import HTTPServer, BaseHTTPRequestHandler
        
        # 等待成为领导节点
        while self.running and not self.election.is_leader():
            time.sleep(1)
        
        if not self.running:
            return
        
        # 启动API服务器
        node = self
        
        class APIHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == '/health':
                    self._send_json({"status": "healthy"})
                elif self.path == '/status':
                    self._send_json(node.get_status())
                elif self.path == '/nodes':
                    self._send_json({
                        "nodes": [n.to_dict() for n in node.known_nodes.values()]
                    })
                elif self.path == '/stats':
                    self._send_json(node.stats)
                else:
                    self.send_error(404)
            
            def do_POST(self):
                if self.path == '/inference':
                    self._handle_inference()
                elif self.path == '/task':
                    self._handle_task_submit()
                else:
                    self.send_error(404)
            
            def _handle_inference(self):
                content_length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(content_length)
                
                try:
                    data = json.loads(body)
                    prompt = data.get('prompt', '')
                    params = data.get('params', {})
                    
                    # 提交任务
                    task_id = node.scheduler.submit_task(prompt, params)
                    
                    # 等待结果
                    max_wait = params.get('timeout', 60)
                    start = time.time()
                    
                    while time.time() - start < max_wait:
                        with node.scheduler.lock:
                            if task_id in node.scheduler.completed_tasks:
                                task = node.scheduler.completed_tasks[task_id]
                                self._send_json({
                                    "success": True,
                                    "task_id": task_id,
                                    "response": task.result,
                                    "tokens": task.tokens,
                                    "latency": task.latency,
                                })
                                return
                            if task_id in node.scheduler.running_tasks:
                                # 任务正在运行
                                pass
                        
                        time.sleep(0.1)
                    
                    self._send_json({"success": False, "error": "超时"})
                    
                except Exception as e:
                    self._send_json({"success": False, "error": str(e)}, 500)
            
            def _handle_task_submit(self):
                content_length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(content_length)
                
                try:
                    data = json.loads(body)
                    prompt = data.get('prompt', '')
                    params = data.get('params', {})
                    
                    task_id = node.scheduler.submit_task(prompt, params)
                    
                    self._send_json({
                        "success": True,
                        "task_id": task_id,
                    })
                    
                except Exception as e:
                    self._send_json({"success": False, "error": str(e)}, 500)
            
            def _send_json(self, data, code=200):
                self.send_response(code)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps(data, ensure_ascii=False).encode())
            
            def log_message(self, format, *args):
                pass
        
        try:
            api_port = self.config.api_port
            server = HTTPServer(('0.0.0.0', api_port), APIHandler)
            print(f"[API] API服务启动: http://0.0.0.0:{api_port}")
            server.serve_forever()
        except Exception as e:
            print(f"[API] 启动失败: {e}")
    
    def get_status(self) -> Dict:
        """获取状态"""
        return {
            "node_id": self.node_id,
            "node_name": self.config.node_name,
            "role": self.node_info.role.value,
            "state": self.state.value,
            "is_leader": self.election.is_leader(),
            "leader_id": self.election.get_leader(),
            "term": self.election.current_term,
            "model_loaded": self.model.loaded,
            "model_name": self.config.model_name,
            "known_nodes": len(self.known_nodes),
            "pending_tasks": len(self.scheduler.pending_tasks),
            "running_tasks": len(self.scheduler.running_tasks),
            "active_tasks": self.node_info.active_tasks,
            "stats": self.stats,
            "resources": {
                "memory_available_gb": self.node_info.memory_available_gb,
                "cpu_percent": self.node_info.cpu_percent,
                "gpu_available": self.node_info.gpu_available,
            },
        }
    
    def stop(self):
        """停止节点"""
        print("\n[节点] 正在停止...")
        self.running = False
        self.state = NodeState.STOPPING
        
        self.election.stop()
        self.discovery.stop()
        self.network.stop()
        self.model.unload()
        
        print("[节点] 已停止")


# ==================== 主函数 ====================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="分布式大模型推理系统 - 统一去中心化节点",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    # 第一个节点（自动成为领导）
    python node_unified.py --port 5000 --api-port 8080
    
    # 后续节点（自动发现并加入）
    python node_unified.py --port 5001 --seeds "192.168.1.100:5000"
    
    # 指定模型
    python node_unified.py --port 5000 --model Qwen/Qwen2.5-1.5B-Instruct

API端点 (领导节点):
    POST /inference - 提交推理请求
    POST /task      - 提交异步任务
    GET  /status    - 获取节点状态
    GET  /nodes     - 获取节点列表
    GET  /stats     - 获取统计信息
        """
    )
    
    parser.add_argument("--host", default="0.0.0.0", help="监听地址")
    parser.add_argument("--port", "-p", type=int, default=5000, help="节点通信端口")
    parser.add_argument("--api-port", type=int, default=8080, help="API服务端口")
    parser.add_argument("--name", "-n", default=None, help="节点名称")
    parser.add_argument("--model", "-m", default="Qwen/Qwen2.5-0.5B-Instruct", help="模型名称")
    parser.add_argument("--seeds", "-s", default="", help="种子节点列表，逗号分隔")
    parser.add_argument("--workers", "-w", type=int, default=2, help="并行工作线程")
    parser.add_argument("--min-memory", type=float, default=2.0, help="最小内存(GB)")
    
    args = parser.parse_args()
    
    # 解析种子节点
    seeds = []
    if args.seeds:
        seeds = [s.strip() for s in args.seeds.split(",")]
    
    config = UnifiedConfig(
        node_name=args.name,
        host=args.host,
        port=args.port,
        api_port=args.api_port,
        model_name=args.model,
        seeds=seeds,
        max_workers=args.workers,
        min_memory_gb=args.min_memory,
    )
    
    node = UnifiedNode(config)
    
    def signal_handler(sig, frame):
        print("\n停止服务...")
        node.stop()
        sys.exit(0)
    
    import signal
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        node.start()
        
        # 主循环
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        node.stop()


if __name__ == "__main__":
    main()
