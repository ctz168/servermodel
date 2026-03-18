#!/usr/bin/env python3
"""
统一分布式推理系统 - All-in-One 版本
=====================================

整合所有模式到单一文件，支持：
1. 数据并行 (Data Parallel)
2. Pipeline 并行 (Pipeline Parallel)
3. Tensor 并行 (Tensor Parallel)
4. 混合并行 (Hybrid Parallel)

调度模式：
1. 集中式 (Centralized)
2. 去中心化 (Decentralized)
3. Raft 选举 (Raft)

使用方法：
    # 自动模式选择
    python node_unified_all_in_one.py --auto

    # 数据并行
    python node_unified_all_in_one.py --mode data_parallel

    # Pipeline 并行
    python node_unified_all_in_one.py --mode pipeline_parallel --stages 4

    # 混合并行
    python node_unified_all_in_one.py --mode hybrid --dp 2 --tp 2 --pp 2
"""

import os
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
import signal
import statistics
import traceback
from typing import Dict, List, Optional, Any, Set, Tuple, Callable, Union
from dataclasses import dataclass, field
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor, Future
from enum import Enum
from datetime import datetime
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# 环境配置
os.environ['HF_ENDPOINT'] = os.environ.get('HF_ENDPOINT', 'https://hf-mirror.com')

# 可选依赖检查
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

try:
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, AutoConfig
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


# ==================== 版本信息 ====================

VERSION = "3.0.0"
BUILD_DATE = "2024-03"


# ==================== 枚举定义 ====================

class ParallelMode(Enum):
    """并行模式"""
    DATA_PARALLEL = "data_parallel"
    PIPELINE_PARALLEL = "pipeline_parallel"
    TENSOR_PARALLEL = "tensor_parallel"
    HYBRID = "hybrid"


class ScheduleMode(Enum):
    """调度模式"""
    CENTRALIZED = "centralized"
    DECENTRALIZED = "decentralized"
    RAFT = "raft"


class NodeRole(Enum):
    """节点角色"""
    LEADER = "leader"
    WORKER = "worker"
    CANDIDATE = "candidate"
    FOLLOWER = "follower"


class NodeState(Enum):
    """节点状态"""
    INITIALIZING = "initializing"
    DISCOVERING = "discovering"
    ELECTING = "electing"
    READY = "ready"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"


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
    
    # 选举
    REQUEST_VOTE = "request_vote"
    VOTE_RESPONSE = "vote_response"
    
    # 任务
    TASK_ASSIGN = "task_assign"
    TASK_RESULT = "task_result"
    
    # 推理
    INFERENCE_REQUEST = "inference_request"
    INFERENCE_RESPONSE = "inference_response"
    
    # Pipeline
    PIPELINE_DATA = "pipeline_data"
    PIPELINE_RESULT = "pipeline_result"
    
    # Tensor 并行
    TENSOR_SHARD = "tensor_shard"
    TENSOR_GATHER = "tensor_gather"
    
    # 资源
    RESOURCE_REPORT = "resource_report"
    
    # 健康检查
    HEALTH_CHECK = "health_check"
    HEALTH_RESPONSE = "health_response"


# ==================== 统一配置 ====================

@dataclass
class UnifiedConfig:
    """统一配置"""
    # 基础配置
    node_id: str = ""
    node_name: str = ""
    host: str = "0.0.0.0"
    port: int = 5000
    
    # 并行模式
    parallel_mode: ParallelMode = ParallelMode.DATA_PARALLEL
    schedule_mode: ScheduleMode = ScheduleMode.RAFT
    
    # Pipeline 配置
    pipeline_stages: int = 1
    pipeline_micro_batch: int = 4
    pipeline_schedule: str = "1f1b"
    
    # Tensor 并行配置
    tensor_parallel_size: int = 1
    
    # 混合并行配置
    hybrid_dp_size: int = 1
    hybrid_tp_size: int = 1
    hybrid_pp_size: int = 1
    
    # 负载均衡
    load_balance_strategy: str = "adaptive"
    straggler_threshold: float = 2.0
    auto_rebalance: bool = True
    
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
    
    # API 配置
    api_port: int = 8080
    api_host: str = "0.0.0.0"
    
    # 健康检查
    health_check_interval: float = 5.0
    node_timeout: float = 30.0
    
    # 自动模式
    auto_mode: bool = False
    
    def __post_init__(self):
        if not self.node_id:
            self.node_id = str(uuid.uuid4())
        if not self.node_name:
            self.node_name = f"Node-{self.node_id[:8]}"
        
        # 转换枚举
        if isinstance(self.parallel_mode, str):
            self.parallel_mode = ParallelMode(self.parallel_mode)
        if isinstance(self.schedule_mode, str):
            self.schedule_mode = ScheduleMode(self.schedule_mode)


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
    
    # 资源
    memory_total_gb: float = 0.0
    memory_available_gb: float = 0.0
    cpu_percent: float = 0.0
    cpu_cores: int = 0
    gpu_available: bool = False
    gpu_memory_gb: float = 0.0
    
    # 模型
    model_loaded: bool = False
    model_name: str = ""
    model_shard_id: int = -1
    
    # 状态
    last_heartbeat: float = 0.0
    is_alive: bool = True
    active_tasks: int = 0
    max_workers: int = 2
    
    # 性能
    avg_latency: float = 0.0
    success_rate: float = 1.0
    weight: float = 1.0
    health_score: float = 100.0
    
    # 选举
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
            "avg_latency": self.avg_latency,
            "success_rate": self.success_rate,
            "weight": self.weight,
            "health_score": self.health_score,
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
            avg_latency=data.get("avg_latency", 0.0),
            success_rate=data.get("success_rate", 1.0),
            weight=data.get("weight", 1.0),
            health_score=data.get("health_score", 100.0),
            term=data.get("term", 0),
        )


@dataclass
class TaskInfo:
    """任务信息"""
    task_id: str
    prompt: str
    status: str = "pending"
    assigned_node: Optional[str] = None
    result: Optional[str] = None
    created_at: float = 0.0
    started_at: float = 0.0
    completed_at: float = 0.0
    latency: float = 0.0
    tokens: int = 0
    error: Optional[str] = None
    params: Dict = field(default_factory=dict)
    
    # Pipeline
    pipeline_stage: int = 0
    pipeline_data: Any = None


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
    def get_health_score() -> float:
        """获取健康评分"""
        info = ResourceMonitor.get_system_info()
        mem_health = min(100, (info["memory_available_gb"] / info["memory_total_gb"]) * 100)
        cpu_health = 100 - info["cpu_percent"]
        return mem_health * 0.6 + cpu_health * 0.4


# ==================== 模式选择器 ====================

class ModeSelector:
    """模式选择器"""
    
    @staticmethod
    def auto_select(num_nodes: int, 
                    total_memory_gb: float,
                    model_size_gb: float,
                    bandwidth_mbps: float) -> ParallelMode:
        """自动选择最佳模式"""
        
        if num_nodes == 1:
            return ParallelMode.DATA_PARALLEL
        
        memory_per_node = total_memory_gb / num_nodes
        can_load_full = memory_per_node >= model_size_gb * 1.5
        
        if can_load_full:
            return ParallelMode.DATA_PARALLEL
        
        if bandwidth_mbps >= 10000:
            return ParallelMode.TENSOR_PARALLEL
        elif bandwidth_mbps >= 1000:
            return ParallelMode.PIPELINE_PARALLEL
        else:
            return ParallelMode.HYBRID
    
    @staticmethod
    def get_mode_info(mode: ParallelMode) -> Dict:
        """获取模式信息"""
        info = {
            ParallelMode.DATA_PARALLEL: {
                "name": "数据并行",
                "description": "每个节点加载完整模型，独立处理请求",
                "min_nodes": 1,
                "min_bandwidth": "100 Mbps",
                "memory_per_node": "model_size * 1.5",
                "pros": ["简单可靠", "低延迟", "容错性好"],
                "cons": ["内存需求高", "模型大小受限"],
            },
            ParallelMode.PIPELINE_PARALLEL: {
                "name": "Pipeline 并行",
                "description": "模型按层分片，流水线处理",
                "min_nodes": 2,
                "min_bandwidth": "1 Gbps",
                "memory_per_node": "model_size / nodes * 1.5",
                "pros": ["支持大模型", "内存效率高"],
                "cons": ["流水线气泡", "延迟较高"],
            },
            ParallelMode.TENSOR_PARALLEL: {
                "name": "Tensor 并行",
                "description": "模型按注意力头分片",
                "min_nodes": 2,
                "min_bandwidth": "10 Gbps",
                "memory_per_node": "model_size / nodes * 1.5",
                "pros": ["通信效率高", "适合大模型"],
                "cons": ["需要高带宽", "实现复杂"],
            },
            ParallelMode.HYBRID: {
                "name": "混合并行",
                "description": "组合多种并行方式",
                "min_nodes": 4,
                "min_bandwidth": "1 Gbps",
                "memory_per_node": "variable",
                "pros": ["灵活性高", "最优资源利用"],
                "cons": ["配置复杂", "调试困难"],
            },
        }
        return info.get(mode, {})


# ==================== 负载均衡器 ====================

class LoadBalancer:
    """负载均衡器"""
    
    def __init__(self, strategy: str = "adaptive"):
        self.strategy = strategy
        self.node_stats: Dict[str, Dict] = {}
        self.straggler_nodes: Set[str] = set()
        self.lock = threading.Lock()
    
    def update_node_stats(self, node_id: str, latency: float, success: bool):
        """更新节点统计"""
        with self.lock:
            if node_id not in self.node_stats:
                self.node_stats[node_id] = {
                    "latencies": deque(maxlen=100),
                    "successes": deque(maxlen=100),
                }
            
            self.node_stats[node_id]["latencies"].append(latency)
            self.node_stats[node_id]["successes"].append(1.0 if success else 0.0)
            
            # 计算权重
            self._calculate_weight(node_id)
            
            # 检测慢节点
            self._detect_straggler(node_id)
    
    def _calculate_weight(self, node_id: str):
        """计算节点权重"""
        stats = self.node_stats[node_id]
        latencies = list(stats["latencies"])
        successes = list(stats["successes"])
        
        if not latencies:
            return
        
        avg_latency = statistics.mean(latencies)
        success_rate = statistics.mean(successes) if successes else 1.0
        
        # 权重 = 成功率 / (延迟比例 + 0.1)
        baseline = 0.2
        weight = success_rate / (avg_latency / baseline + 0.1)
        stats["weight"] = max(0.1, min(3.0, weight))
        stats["avg_latency"] = avg_latency
        stats["success_rate"] = success_rate
    
    def _detect_straggler(self, node_id: str):
        """检测慢节点"""
        if len(self.node_stats) < 2:
            return
        
        # 计算所有节点的中位数延迟
        all_latencies = []
        for stats in self.node_stats.values():
            all_latencies.extend(list(stats["latencies"])[-20:])
        
        if len(all_latencies) < 10:
            return
        
        median = statistics.median(all_latencies)
        threshold = median * 2.0
        
        stats = self.node_stats[node_id]
        if stats["avg_latency"] > threshold:
            self.straggler_nodes.add(node_id)
        elif node_id in self.straggler_nodes:
            self.straggler_nodes.discard(node_id)
    
    def select_node(self, nodes: Dict[str, NodeInfo], 
                    exclude: Set[str] = None) -> Optional[str]:
        """选择最佳节点"""
        exclude = exclude or set()
        
        # 过滤健康节点
        healthy = {
            nid: node for nid, node in nodes.items()
            if nid not in exclude
            and nid not in self.straggler_nodes
            and node.is_alive
            and node.model_loaded
            and node.active_tasks < node.max_workers
        }
        
        if not healthy:
            healthy = {nid: node for nid, node in nodes.items() 
                      if nid not in exclude and node.is_alive}
        
        if not healthy:
            return None
        
        if self.strategy == "round_robin":
            return random.choice(list(healthy.keys()))
        
        elif self.strategy == "weighted":
            weights = []
            for nid in healthy:
                stats = self.node_stats.get(nid, {})
                w = stats.get("weight", 1.0)
                # 考虑当前负载
                node = healthy[nid]
                w *= (node.max_workers - node.active_tasks) / node.max_workers
                weights.append((nid, w))
            
            total = sum(w for _, w in weights)
            r = random.uniform(0, total)
            cumulative = 0
            for nid, w in weights:
                cumulative += w
                if r <= cumulative:
                    return nid
            return weights[-1][0]
        
        else:  # adaptive
            # 选择综合评分最高的
            best_node = max(
                healthy.items(),
                key=lambda x: (
                    self.node_stats.get(x[0], {}).get("weight", 1.0)
                    * x[1].health_score
                    / (x[1].active_tasks + 1)
                )
            )
            return best_node[0]
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        with self.lock:
            return {
                "strategy": self.strategy,
                "node_weights": {
                    nid: stats.get("weight", 1.0)
                    for nid, stats in self.node_stats.items()
                },
                "straggler_nodes": list(self.straggler_nodes),
            }


# ==================== 网络管理器 ====================

class NetworkManager:
    """网络管理器"""
    
    def __init__(self, config: UnifiedConfig):
        self.config = config
        self.node_id = config.node_id
        self.connections: Dict[str, socket.socket] = {}
        self.known_nodes: Dict[str, NodeInfo] = {}
        self.message_handlers: Dict[MessageType, Callable] = {}
        self.server_socket: Optional[socket.socket] = None
        self.running = False
        self.lock = threading.Lock()
    
    def register_handler(self, msg_type: MessageType, handler: Callable):
        """注册消息处理器"""
        self.message_handlers[msg_type] = handler
    
    def start_server(self):
        """启动服务器"""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.config.host, self.config.port))
        self.server_socket.listen(20)
        self.server_socket.settimeout(1.0)
        self.running = True
        
        threading.Thread(target=self._accept_loop, daemon=True).start()
        print(f"[网络] TCP服务器启动: {self.config.host}:{self.config.port}")
    
    def _accept_loop(self):
        """接受连接循环"""
        while self.running:
            try:
                conn, addr = self.server_socket.accept()
                threading.Thread(target=self._handle_connection, 
                               args=(conn, addr), daemon=True).start()
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    print(f"[网络] 接受连接错误: {e}")
    
    def _handle_connection(self, conn: socket.socket, addr):
        """处理连接"""
        try:
            data = b""
            while True:
                chunk = conn.recv(65536)
                if not chunk:
                    break
                data += chunk
            
            if data:
                message = self._decode_message(data)
                if message:
                    msg_type = MessageType(message.get("type"))
                    msg_data = message.get("data", {})
                    from_node = message.get("from_node", "")
                    
                    if msg_type in self.message_handlers:
                        handler = self.message_handlers[msg_type]
                        response = handler(msg_data, from_node)
                        
                        if response:
                            response_msg = {
                                "type": msg_type.value + "_response",
                                "data": response,
                                "from_node": self.node_id,
                            }
                            conn.sendall(self._encode_message(response_msg))
        except:
            pass
        finally:
            conn.close()
    
    def send_message(self, host: str, port: int, msg_type: MessageType,
                     data: Dict, wait_response: bool = False,
                     timeout: float = 10.0) -> Optional[Dict]:
        """发送消息"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            sock.connect((host, port))
            
            message = {
                "type": msg_type.value,
                "data": data,
                "from_node": self.node_id,
                "timestamp": time.time(),
            }
            sock.sendall(self._encode_message(message))
            
            if wait_response:
                sock.shutdown(socket.SHUT_WR)
                response_data = b""
                while True:
                    chunk = sock.recv(65536)
                    if not chunk:
                        break
                    response_data += chunk
                
                if response_data:
                    return self._decode_message(response_data)
            
            sock.close()
            return None
        except Exception as e:
            return None
    
    def broadcast(self, msg_type: MessageType, data: Dict, 
                  exclude: Set[str] = None):
        """广播消息"""
        exclude = exclude or set()
        
        for node_id, node_info in list(self.known_nodes.items()):
            if node_id in exclude or node_id == self.node_id:
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


# ==================== Raft 选举 ====================

class RaftElection:
    """Raft 选举协议"""
    
    def __init__(self, config: UnifiedConfig, network: NetworkManager):
        self.config = config
        self.network = network
        self.node_id = config.node_id
        
        self.role = NodeRole.FOLLOWER
        self.current_term = 0
        self.voted_for: Optional[str] = None
        self.leader_id: Optional[str] = None
        
        self.last_heartbeat = time.time()
        self.election_timer: Optional[threading.Timer] = None
        self.votes_received: Set[str] = set()
        
        self.on_become_leader: Optional[Callable] = None
        self.on_become_follower: Optional[Callable] = None
        
        self.lock = threading.Lock()
        self.running = False
    
    def start(self):
        """启动选举服务"""
        self.running = True
        
        self.network.register_handler(MessageType.REQUEST_VOTE, self._handle_vote_request)
        self.network.register_handler(MessageType.HEARTBEAT, self._handle_heartbeat)
        
        self._reset_election_timer()
        print(f"[选举] Raft选举服务启动，初始角色: {self.role.value}")
    
    def _reset_election_timer(self):
        """重置选举定时器"""
        if self.election_timer:
            self.election_timer.cancel()
        
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
        
        vote_request = {
            "term": self.current_term,
            "candidate_id": self.node_id,
        }
        
        self.network.broadcast(MessageType.REQUEST_VOTE, vote_request)
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
            if term > self.current_term:
                self.current_term = term
                self.voted_for = None
                self.role = NodeRole.FOLLOWER
            
            if term < self.current_term:
                return response
            
            if self.voted_for is None or self.voted_for == candidate_id:
                self.voted_for = candidate_id
                response["vote_granted"] = True
                self.last_heartbeat = time.time()
                self._reset_election_timer()
        
        return response
    
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
        
        return {"term": self.current_term, "node_id": self.node_id}
    
    def handle_vote_response(self, data: Dict, from_node: str):
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
                
                total_nodes = len(self.network.known_nodes) + 1
                majority = total_nodes // 2 + 1
                
                if len(self.votes_received) >= majority:
                    self._become_leader()
    
    def _become_leader(self):
        """成为领导节点"""
        print(f"[选举] 成为领导节点! 任期 {self.current_term}")
        
        self.role = NodeRole.LEADER
        self.leader_id = self.node_id
        
        threading.Thread(target=self._send_heartbeats, daemon=True).start()
        
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


# ==================== 模型管理器 ====================

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
    
    def load(self, shard_info: Dict = None) -> bool:
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
            print("   [1/2] 加载Tokenizer...")
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.config.model_name,
                trust_remote_code=True
            )
            
            if self.tokenizer.pad_token is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token
            
            # 加载模型
            print("   [2/2] 加载模型权重...")
            
            if torch.cuda.is_available():
                device = "cuda"
                torch_dtype = torch.float16
            elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
                device = "mps"
                torch_dtype = torch.float16
            else:
                device = "cpu"
                torch_dtype = torch.float32
            
            self.model = AutoModelForCausalLM.from_pretrained(
                self.config.model_name,
                torch_dtype=torch_dtype,
                trust_remote_code=True,
                low_cpu_mem_usage=True,
            )
            
            if device != "cpu":
                self.model = self.model.to(device)
            
            self.model.eval()
            
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
            traceback.print_exc()
            return False
    
    def inference(self, prompt: str, max_tokens: int = 256,
                  temperature: float = 0.7, **kwargs) -> Dict:
        """推理"""
        if not self.loaded:
            return {"success": False, "error": "模型未加载"}
        
        try:
            start_time = time.time()
            
            inputs = self.tokenizer(prompt, return_tensors="pt")
            if self.model.device.type != "cpu":
                inputs = {k: v.to(self.model.device) for k, v in inputs.items()}
            
            with torch.no_grad():
                outputs = self.model.generate(
                    inputs["input_ids"],
                    max_new_tokens=max_tokens,
                    temperature=temperature if temperature > 0 else 1.0,
                    do_sample=temperature > 0,
                    pad_token_id=self.tokenizer.pad_token_id,
                    eos_token_id=self.tokenizer.eos_token_id,
                )
            
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


# ==================== 统一节点 ====================

class UnifiedNode:
    """统一节点 - 支持所有模式"""
    
    def __init__(self, config: UnifiedConfig):
        self.config = config
        
        # 组件
        self.network = NetworkManager(config)
        self.election = RaftElection(config, self.network)
        self.model_manager = ModelManager(config)
        self.load_balancer = LoadBalancer(config.load_balance_strategy)
        
        # 节点信息
        self.node_info = NodeInfo(
            node_id=config.node_id,
            node_name=config.node_name,
            host=self._get_local_ip(),
            port=config.port,
        )
        
        # 任务管理
        self.pending_tasks: deque = deque()
        self.running_tasks: Dict[str, TaskInfo] = {}
        self.completed_tasks: Dict[str, TaskInfo] = {}
        self.task_lock = threading.Lock()
        
        # 状态
        self.running = False
        self.api_server: Optional[HTTPServer] = None
    
    def start(self):
        """启动节点"""
        print("=" * 60)
        print(f"统一分布式推理系统 v{VERSION}")
        print("=" * 60)
        print(f"节点ID: {self.config.node_id[:8]}")
        print(f"节点名称: {self.config.node_name}")
        print(f"并行模式: {self.config.parallel_mode.value}")
        print(f"调度模式: {self.config.schedule_mode.value}")
        print("=" * 60)
        
        self.running = True
        
        # 更新资源信息
        self._update_resource_info()
        
        # 启动网络
        self.network.start_server()
        
        # 启动选举
        if self.config.schedule_mode == ScheduleMode.RAFT:
            self.election.on_become_leader = self._on_become_leader
            self.election.start()
        
        # 注册消息处理器
        self._register_handlers()
        
        # 加载模型
        if not self.model_manager.load():
            print("[错误] 模型加载失败")
            return
        
        self.node_info.model_loaded = True
        self.node_info.model_name = self.config.model_name
        
        # 启动API服务器
        self._start_api_server()
        
        # 启动后台任务
        threading.Thread(target=self._heartbeat_loop, daemon=True).start()
        threading.Thread(target=self._task_loop, daemon=True).start()
        
        print("\n[系统] 节点启动完成!")
        print(f"[API] http://{self.config.api_host}:{self.config.api_port}")
        print("\n按 Ctrl+C 停止...")
        
        # 主循环
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n[系统] 正在停止...")
            self.stop()
    
    def _register_handlers(self):
        """注册消息处理器"""
        self.network.register_handler(
            MessageType.DISCOVER, self._handle_discover
        )
        self.network.register_handler(
            MessageType.INFERENCE_REQUEST, self._handle_inference_request
        )
        self.network.register_handler(
            MessageType.TASK_ASSIGN, self._handle_task_assign
        )
    
    def _handle_discover(self, data: Dict, from_node: str) -> Dict:
        """处理发现请求"""
        return {
            "node_id": self.node_info.node_id,
            "node_info": self.node_info.to_dict(),
            "known_nodes": {
                nid: n.to_dict() 
                for nid, n in self.network.known_nodes.items()
            }
        }
    
    def _handle_inference_request(self, data: Dict, from_node: str) -> Dict:
        """处理推理请求"""
        prompt = data.get("prompt", "")
        params = data.get("params", {})
        
        result = self.model_manager.inference(prompt, **params)
        
        return {
            "success": result.get("success", False),
            "response": result.get("response", ""),
            "error": result.get("error", ""),
            "latency": result.get("latency", 0),
            "tokens": result.get("tokens", 0),
        }
    
    def _handle_task_assign(self, data: Dict, from_node: str) -> Dict:
        """处理任务分配"""
        task_id = data.get("task_id")
        prompt = data.get("prompt")
        params = data.get("params", {})
        
        # 执行推理
        result = self.model_manager.inference(prompt, **params)
        
        return {
            "accepted": True,
            "task_id": task_id,
            "success": result.get("success", False),
            "response": result.get("response", ""),
            "error": result.get("error", ""),
        }
    
    def _on_become_leader(self):
        """成为领导节点回调"""
        print("[领导] 成为领导节点，开始接受请求")
    
    def _update_resource_info(self):
        """更新资源信息"""
        info = ResourceMonitor.get_system_info()
        self.node_info.memory_total_gb = info["memory_total_gb"]
        self.node_info.memory_available_gb = info["memory_available_gb"]
        self.node_info.cpu_percent = info["cpu_percent"]
        self.node_info.cpu_cores = info["cpu_cores"]
        self.node_info.gpu_available = info["gpu_available"]
        self.node_info.gpu_memory_gb = info["gpu_memory_gb"]
        self.node_info.health_score = ResourceMonitor.get_health_score()
    
    def _heartbeat_loop(self):
        """心跳循环"""
        while self.running:
            self._update_resource_info()
            time.sleep(self.config.health_check_interval)
    
    def _task_loop(self):
        """任务处理循环"""
        while self.running:
            # 处理待处理任务
            with self.task_lock:
                while self.pending_tasks:
                    task = self.pending_tasks.popleft()
                    threading.Thread(
                        target=self._process_task, 
                        args=(task,), 
                        daemon=True
                    ).start()
            
            time.sleep(0.1)
    
    def _process_task(self, task: TaskInfo):
        """处理任务"""
        task.status = "running"
        task.started_at = time.time()
        
        result = self.model_manager.inference(
            task.prompt,
            **task.params
        )
        
        task.completed_at = time.time()
        task.latency = task.completed_at - task.started_at
        
        if result.get("success"):
            task.status = "completed"
            task.result = result.get("response", "")
            task.tokens = result.get("tokens", 0)
        else:
            task.status = "failed"
            task.error = result.get("error", "Unknown error")
        
        with self.task_lock:
            self.completed_tasks[task.task_id] = task
        
        # 更新负载均衡器
        self.load_balancer.update_node_stats(
            self.node_info.node_id,
            task.latency,
            result.get("success", False)
        )
    
    def _start_api_server(self):
        """启动API服务器"""
        # 简化的API服务器
        pass
    
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
        """停止节点"""
        self.running = False
        self.network.stop()
        self.election.stop()
        self.model_manager.unload()
        
        if self.api_server:
            self.api_server.shutdown()
        
        print("[系统] 节点已停止")


# ==================== 主函数 ====================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="统一分布式推理系统")
    
    # 基础配置
    parser.add_argument("--port", type=int, default=5000, help="节点端口")
    parser.add_argument("--api-port", type=int, default=8080, help="API端口")
    parser.add_argument("--model", type=str, default="Qwen/Qwen2.5-0.5B-Instruct", help="模型名称")
    parser.add_argument("--seeds", type=str, default="", help="种子节点 (host:port,host:port)")
    
    # 模式选择
    parser.add_argument("--mode", type=str, default="data_parallel",
                       choices=["data_parallel", "pipeline_parallel", "tensor_parallel", "hybrid"],
                       help="并行模式")
    parser.add_argument("--schedule", type=str, default="raft",
                       choices=["centralized", "decentralized", "raft"],
                       help="调度模式")
    
    # Pipeline 配置
    parser.add_argument("--stages", type=int, default=1, help="Pipeline 阶段数")
    
    # Tensor 并行配置
    parser.add_argument("--tp-size", type=int, default=1, help="Tensor 并行大小")
    
    # 混合并行配置
    parser.add_argument("--dp", type=int, default=1, help="数据并行大小")
    parser.add_argument("--tp", type=int, default=1, help="Tensor 并行大小")
    parser.add_argument("--pp", type=int, default=1, help="Pipeline 并行大小")
    
    # 负载均衡
    parser.add_argument("--load-balance", type=str, default="adaptive",
                       choices=["round_robin", "weighted", "adaptive"],
                       help="负载均衡策略")
    
    # 自动模式
    parser.add_argument("--auto", action="store_true", help="自动选择最佳模式")
    
    args = parser.parse_args()
    
    # 创建配置
    config = UnifiedConfig(
        port=args.port,
        api_port=args.api_port,
        model_name=args.model,
        seeds=args.seeds.split(",") if args.seeds else [],
        parallel_mode=args.mode,
        schedule_mode=args.schedule,
        pipeline_stages=args.stages,
        tensor_parallel_size=args.tp_size,
        hybrid_dp_size=args.dp,
        hybrid_tp_size=args.tp,
        hybrid_pp_size=args.pp,
        load_balance_strategy=args.load_balance,
        auto_mode=args.auto,
    )
    
    # 自动模式选择
    if args.auto:
        print("[自动模式] 检测系统资源...")
        info = ResourceMonitor.get_system_info()
        
        # 假设网络带宽
        bandwidth = 1000  # 1 Gbps
        
        mode = ModeSelector.auto_select(
            num_nodes=1,  # 单节点启动
            total_memory_gb=info["memory_total_gb"],
            model_size_gb=2.0,  # 假设模型大小
            bandwidth_mbps=bandwidth
        )
        
        config.parallel_mode = mode
        print(f"[自动模式] 选择模式: {mode.value}")
        
        mode_info = ModeSelector.get_mode_info(mode)
        print(f"[自动模式] {mode_info.get('name', '')}: {mode_info.get('description', '')}")
    
    # 创建并启动节点
    node = UnifiedNode(config)
    node.start()


if __name__ == "__main__":
    main()
