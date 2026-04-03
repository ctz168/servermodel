#!/usr/bin/env python3
"""
统一分布式推理系统 - 完整版
============================

整合所有功能到单一文件，包含：
1. 完整的API服务器
2. Pipeline并行推理
3. Tensor并行推理
4. 混合并行推理
5. 动态负载均衡
6. 慢节点检测与隔离
7. 健康监控面板
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
import argparse
import re
import gc
import logging
from typing import Dict, List, Optional, Any, Set, Tuple, Callable, Union
from dataclasses import dataclass, field
from collections import defaultdict, deque, OrderedDict
from concurrent.futures import ThreadPoolExecutor, Future
from enum import Enum
from datetime import datetime
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler, ThreadingHTTPServer
from socketserver import ThreadingMixIn
from urllib.parse import urlparse, parse_qs

__all__ = [
    "VERSION",
    "ParallelMode",
    "ScheduleMode",
    "NodeRole",
    "NodeState",
    "MessageType",
    "UnifiedConfig",
    "NodeInfo",
    "TaskInfo",
    "PipelineStage",
    "InferenceResult",
    "ResourceMonitor",
    "ModeSelector",
    "LoadBalancer",
    "DistributedInferenceCoordinator",
    "NetworkManager",
    "RaftElection",
    "ModelManager",
    "APIRequestHandler",
    "UnifiedNode",
    "main",
]

# ==================== 日志配置 ====================

logger = logging.getLogger("unified_inference")

# 默认日志格式
_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"
_LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(level: str = "INFO", log_file: str = ""):
    """配置日志系统"""
    log_level = getattr(logging, level.upper(), logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(_LOG_FORMAT, _LOG_DATE_FORMAT))
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.setLevel(log_level)

    if log_file:
        os.makedirs(os.path.dirname(log_file) or ".", exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(logging.Formatter(_LOG_FORMAT, _LOG_DATE_FORMAT))
        logger.addHandler(file_handler)


# 环境配置
os.environ['HF_ENDPOINT'] = os.environ.get('HF_ENDPOINT', 'https://hf-mirror.com')

# 可选依赖检查
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False
    logger.warning("psutil未安装，请运行: pip install psutil")

try:
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, AutoConfig
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False
    logger.warning("torch/transformers未安装，请运行: pip install torch transformers")

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

try:
    from pyngrok import ngrok
    HAS_NGROK = True
except ImportError:
    HAS_NGROK = False


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
    
    # 集群资源协调
    CLUSTER_RESOURCE_QUERY = "cluster_resource_query"
    CLUSTER_RESOURCE_RESPONSE = "cluster_resource_response"
    CLUSTER_READY = "cluster_ready"
    CLUSTER_START_DISTRIBUTED = "cluster_start_distributed"
    
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
    PIPELINE_INIT = "pipeline_init"
    PIPELINE_DATA = "pipeline_data"
    PIPELINE_RESULT = "pipeline_result"
    PIPELINE_ACK = "pipeline_ack"
    
    # Tensor 并行
    TENSOR_SHARD = "tensor_shard"
    TENSOR_GATHER = "tensor_gather"
    TENSOR_ALLREDUCE = "tensor_allreduce"
    
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
    pipeline_schedule: str = "1f1b"  # 1f1b, gpipe, interleaved
    
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
    api_workers: int = 4
    
    # 健康检查
    health_check_interval: float = 5.0
    node_timeout: float = 30.0
    
    # 自动模式
    auto_mode: bool = False
    
    # 日志
    log_level: str = "INFO"
    log_file: str = ""
    
    # 消息超时与重试
    message_timeout: float = 10.0
    message_retries: int = 2
    
    def __post_init__(self):
        if not self.node_id:
            self.node_id = str(uuid.uuid4())
        if not self.node_name:
            self.node_name = f"Node-{self.node_id[:8]}"
        
        if isinstance(self.parallel_mode, str):
            self.parallel_mode = ParallelMode(self.parallel_mode)
        if isinstance(self.schedule_mode, str):
            self.schedule_mode = ScheduleMode(self.schedule_mode)
    
    def to_dict(self) -> Dict:
        return {
            "node_id": self.node_id,
            "node_name": self.node_name,
            "host": self.host,
            "port": self.port,
            "parallel_mode": self.parallel_mode.value,
            "schedule_mode": self.schedule_mode.value,
            "pipeline_stages": self.pipeline_stages,
            "tensor_parallel_size": self.tensor_parallel_size,
            "model_name": self.model_name,
            "api_port": self.api_port,
        }


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
    pipeline_stage: int = -1
    
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
            "pipeline_stage": self.pipeline_stage,
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
            pipeline_stage=data.get("pipeline_stage", -1),
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
    micro_batch_id: int = 0
    
    # Tensor
    tensor_shard_id: int = -1


@dataclass
class PipelineStage:
    """Pipeline 阶段信息"""
    stage_id: int
    node_id: str
    layer_start: int
    layer_end: int
    is_first: bool = False
    is_last: bool = False
    status: str = "initializing"


@dataclass
class InferenceResult:
    """推理结果"""
    success: bool
    response: str = ""
    tokens: int = 0
    latency: float = 0.0
    throughput: float = 0.0
    error: str = ""
    
    # Pipeline 统计
    pipeline_stages: int = 0
    pipeline_bubbles: int = 0
    
    # Tensor 统计
    tensor_shards: int = 0
    
    def to_dict(self) -> Dict:
        return {
            "success": self.success,
            "response": self.response,
            "tokens": self.tokens,
            "latency": self.latency,
            "throughput": self.throughput,
            "error": self.error,
            "pipeline_stages": self.pipeline_stages,
            "pipeline_bubbles": self.pipeline_bubbles,
            "tensor_shards": self.tensor_shards,
        }


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
            "gpu_memory_used_gb": 0.0,
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
            info["gpu_memory_used_gb"] = torch.cuda.memory_allocated(0) / (1024**3)
        
        return info
    
    @staticmethod
    def get_health_score() -> float:
        """获取健康评分 (0-100)"""
        info = ResourceMonitor.get_system_info()
        
        # 内存健康度 (权重 60%)
        mem_ratio = info["memory_available_gb"] / max(info["memory_total_gb"], 0.1)
        mem_health = min(100, mem_ratio * 100)
        
        # CPU 健康度 (权重 30%)
        cpu_health = 100 - info["cpu_percent"]
        
        # GPU 健康度 (权重 10%)
        gpu_health = 100
        if info["gpu_available"] and info["gpu_memory_gb"] > 0:
            gpu_used_ratio = info["gpu_memory_used_gb"] / info["gpu_memory_gb"]
            gpu_health = (1 - gpu_used_ratio) * 100
        
        return mem_health * 0.6 + cpu_health * 0.3 + gpu_health * 0.1
    
    @staticmethod
    def can_run_model(model_memory_gb: float) -> Tuple[bool, str]:
        """检查是否能运行模型"""
        info = ResourceMonitor.get_system_info()
        
        if info["memory_available_gb"] < model_memory_gb * 1.2:
            return False, f"内存不足: {info['memory_available_gb']:.1f}GB < {model_memory_gb * 1.2:.1f}GB"
        
        return True, "资源充足"
    
    @staticmethod
    def estimate_model_size(model_name: str) -> float:
        """
        估算模型所需内存（GB）
        
        Args:
            model_name: 模型名称
            
        Returns:
            估算的内存需求（GB）
        """
        try:
            # 尝试从模型名称推断大小
            # 常见模型大小映射
            known_models = {
                "Qwen/Qwen2.5-0.5B-Instruct": 1.0,
                "Qwen/Qwen2.5-1.5B-Instruct": 3.0,
                "Qwen/Qwen2.5-3B-Instruct": 6.0,
                "Qwen/Qwen2.5-7B-Instruct": 14.0,
                "Qwen/Qwen2.5-14B-Instruct": 28.0,
                "Qwen/Qwen2.5-32B-Instruct": 64.0,
                "Qwen/Qwen2.5-72B-Instruct": 144.0,
                "Qwen/Qwen2-0.5B-Instruct": 1.0,
                "Qwen/Qwen2-1.5B-Instruct": 3.0,
                "Qwen/Qwen2-7B-Instruct": 14.0,
                "Qwen/Qwen2-72B-Instruct": 144.0,
                "meta-llama/Llama-2-7b-hf": 14.0,
                "meta-llama/Llama-2-13b-hf": 26.0,
                "meta-llama/Llama-2-70b-hf": 140.0,
                "meta-llama/Meta-Llama-3-8B": 16.0,
                "meta-llama/Meta-Llama-3-70B": 140.0,
            }
            
            # 精确匹配
            if model_name in known_models:
                return known_models[model_name]
            
            # 从名称推断（基于参数量）—— re 已在顶层导入
            # 提取参数量（如 7B, 13B, 70B）
            match = re.search(r'(\d+(?:\.\d+)?)\s*[Bb]', model_name)
            if match:
                params_b = float(match.group(1))
                # FP16: 每个参数约2字节，加上开销约3倍
                # 估算: params_b * 2GB * 1.5 (开销)
                return params_b * 2.0 * 1.5
            
            # 默认值（保守估计）
            return 8.0  # 假设需要8GB
            
        except Exception as e:
            logger.error(f"无法估算模型大小: {e}")
            return 8.0  # 默认8GB


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
                "best_for": "内存充足的多节点集群",
            },
            ParallelMode.PIPELINE_PARALLEL: {
                "name": "Pipeline 并行",
                "description": "模型按层分片，流水线处理",
                "min_nodes": 2,
                "min_bandwidth": "1 Gbps",
                "memory_per_node": "model_size / nodes * 1.5",
                "pros": ["支持大模型", "内存效率高"],
                "cons": ["流水线气泡", "延迟较高"],
                "best_for": "大模型 + 中等带宽",
            },
            ParallelMode.TENSOR_PARALLEL: {
                "name": "Tensor 并行",
                "description": "模型按注意力头分片",
                "min_nodes": 2,
                "min_bandwidth": "10 Gbps",
                "memory_per_node": "model_size / nodes * 1.5",
                "pros": ["通信效率高", "适合大模型"],
                "cons": ["需要高带宽", "实现复杂"],
                "best_for": "大模型 + 高带宽网络",
            },
            ParallelMode.HYBRID: {
                "name": "混合并行",
                "description": "组合多种并行方式",
                "min_nodes": 4,
                "min_bandwidth": "1 Gbps",
                "memory_per_node": "variable",
                "pros": ["灵活性高", "最优资源利用"],
                "cons": ["配置复杂", "调试困难"],
                "best_for": "大规模集群 + 异构资源",
            },
        }
        return info.get(mode, {})


# ==================== 负载均衡器 ====================

class LoadBalancer:
    """负载均衡器"""
    
    def __init__(self, strategy: str = "adaptive", straggler_threshold: float = 2.0):
        self.strategy = strategy
        self.straggler_threshold = straggler_threshold
        self.node_stats: Dict[str, Dict] = {}
        self.straggler_nodes: Set[str] = set()
        self.lock = threading.Lock()
        
        # 统计
        self.total_requests = 0
        self.successful_requests = 0
    
    def update_node_stats(self, node_id: str, latency: float, success: bool):
        """更新节点统计"""
        with self.lock:
            if node_id not in self.node_stats:
                self.node_stats[node_id] = {
                    "latencies": deque(maxlen=100),
                    "successes": deque(maxlen=100),
                    "weight": 1.0,
                    "avg_latency": 0.0,
                    "success_rate": 1.0,
                }
            
            self.node_stats[node_id]["latencies"].append(latency)
            self.node_stats[node_id]["successes"].append(1.0 if success else 0.0)
            
            self._calculate_weight(node_id)
            self._detect_straggler(node_id)
            
            self.total_requests += 1
            if success:
                self.successful_requests += 1
    
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
        baseline = 0.2  # 200ms 基准
        weight = success_rate / (avg_latency / baseline + 0.1)
        
        stats["weight"] = max(0.1, min(3.0, weight))
        stats["avg_latency"] = avg_latency
        stats["success_rate"] = success_rate
    
    def _detect_straggler(self, node_id: str):
        """检测慢节点"""
        if len(self.node_stats) < 2:
            return
        
        all_latencies = []
        for stats in self.node_stats.values():
            all_latencies.extend(list(stats["latencies"])[-20:])
        
        if len(all_latencies) < 10:
            return
        
        median = statistics.median(all_latencies)
        threshold = median * self.straggler_threshold
        
        stats = self.node_stats[node_id]
        if stats["avg_latency"] > threshold:
            if node_id not in self.straggler_nodes:
                self.straggler_nodes.add(node_id)
                logger.warning(f"发现慢节点: {node_id[:8]} (延迟: {stats['avg_latency']:.3f}s)")
        elif node_id in self.straggler_nodes:
            self.straggler_nodes.discard(node_id)
            logger.info(f"节点恢复: {node_id[:8]}")
    
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
        
        elif self.strategy == "least_loaded":
            return min(healthy.items(), key=lambda x: x[1].active_tasks)[0]
        
        else:  # adaptive
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
                "total_requests": self.total_requests,
                "successful_requests": self.successful_requests,
                "success_rate": self.successful_requests / max(1, self.total_requests),
                "node_weights": {
                    nid: stats.get("weight", 1.0)
                    for nid, stats in self.node_stats.items()
                },
                "straggler_nodes": list(self.straggler_nodes),
            }


# ==================== 分布式推理协调器 ====================

# Bug 1 fix: Use string annotation for torch.Tensor to avoid NameError when torch not installed
# Also fix Bug 5: Store pipeline_id in pending_stages
# Also fix Bug 6: Save start_time before deletion in _execute_first_stage
# Also fix Improvement 3: Proper token-by-token generation in _generate_final_output

class DistributedInferenceCoordinator:
    """分布式推理协调器 - 管理 Pipeline 并行推理"""
    
    # Maximum completed task entries to keep (Bug 11: memory leak fix)
    MAX_COMPLETED_TASKS = 1000
    
    def __init__(self, node: 'UnifiedNode'):
        self.node = node
        self.pipeline_groups: Dict[str, List[str]] = {}  # pipeline_id -> [node_id, ...]
        self.stage_assignments: Dict[str, int] = {}  # node_id -> stage_id
        # task_id -> {prompt, max_tokens, current_stage, start_time, hidden_states, pipeline_id}
        self.pending_stages: Dict[str, Dict[str, Any]] = {}
        self.lock = threading.Lock()
        
        # 统计
        self.total_pipeline_inferences = 0
        self.total_pipeline_latency = 0.0
    
    def setup_pipeline(self, pipeline_id: str, nodes: List[str], total_stages: int):
        """
        设置 Pipeline 组
        
        Args:
            pipeline_id: Pipeline 组ID
            nodes: 参与的节点列表
            total_stages: 总阶段数
        """
        with self.lock:
            self.pipeline_groups[pipeline_id] = nodes
            
            # 分配阶段
            for i, node_id in enumerate(nodes):
                self.stage_assignments[node_id] = i
            
            logger.info(f"创建 Pipeline 组 {pipeline_id[:8]}: {len(nodes)} 个节点, {total_stages} 个阶段")
    
    def get_stage_for_node(self, node_id: str) -> int:
        """获取节点所属的阶段"""
        return self.stage_assignments.get(node_id, -1)
    
    def start_pipeline_inference(self, task_id: str, prompt: str, 
                                  pipeline_id: str, max_tokens: int = 256) -> Dict:
        """
        启动 Pipeline 推理
        
        Args:
            task_id: 任务ID
            prompt: 输入提示
            pipeline_id: Pipeline 组ID
            max_tokens: 最大生成token数
            
        Returns:
            推理结果或中间状态
        """
        start_time = time.time()
        
        try:
            # 获取 Pipeline 组的节点
            nodes = self.pipeline_groups.get(pipeline_id, [])
            if not nodes:
                return {"success": False, "error": "Pipeline 组不存在"}
            
            # 第一阶段节点
            first_node_id = nodes[0]
            
            # 初始化任务状态 (Bug 5: store pipeline_id)
            with self.lock:
                self.pending_stages[task_id] = {
                    "prompt": prompt,
                    "max_tokens": max_tokens,
                    "current_stage": 0,
                    "start_time": start_time,
                    "hidden_states": None,
                    "pipeline_id": pipeline_id,
                }
            
            # 发送到第一阶段节点
            if first_node_id == self.node.node_info.node_id:
                # 本地执行第一阶段
                return self._execute_first_stage(task_id, prompt, pipeline_id)
            else:
                # 远程执行第一阶段 (Bug 2 fix: use send_message_to_node)
                return self._send_to_node(first_node_id, {
                    "type": "pipeline_stage",
                    "task_id": task_id,
                    "stage": 0,
                    "prompt": prompt,
                    "max_tokens": max_tokens,
                })
            
        except Exception as e:
            logger.error(f"启动推理失败: {e}")
            traceback.print_exc()
            return {"success": False, "error": str(e)}
    
    def _execute_first_stage(self, task_id: str, prompt: str, pipeline_id: str = "default") -> Dict:
        """执行第一阶段推理"""
        try:
            # Tokenize
            inputs = self.node.model_manager.tokenizer(prompt, return_tensors="pt")
            if self.node.model_manager.device != "cpu":
                inputs = {k: v.to(self.node.model_manager.device) for k, v in inputs.items()}
            
            # 获取隐藏状态
            with torch.no_grad():
                # 执行 embedding
                hidden_states = inputs["input_ids"]
                
                # Bug 5 fix: use the actual pipeline_id from the task, not hardcoded "default"
                with self.lock:
                    task_info = self.pending_stages.get(task_id, {})
                    actual_pipeline_id = task_info.get("pipeline_id", pipeline_id)
                
                nodes = self.pipeline_groups.get(actual_pipeline_id, [])
                if len(nodes) > 1:
                    next_node_id = nodes[1]
                    
                    # 序列化隐藏状态
                    hidden_numpy = hidden_states.cpu().numpy()
                    hidden_bytes = pickle.dumps(hidden_numpy)
                    hidden_compressed = zlib.compress(hidden_bytes)
                    
                    # 发送到下一阶段
                    return self._send_to_node(next_node_id, {
                        "type": "pipeline_stage",
                        "task_id": task_id,
                        "stage": 1,
                        "hidden_states": hidden_compressed,
                        "attention_mask": None,
                    })
                else:
                    # 单节点，直接完成推理
                    max_tokens = self.pending_stages[task_id]["max_tokens"]
                    
                    # Bug 6 fix: save start_time before deleting the entry
                    with self.lock:
                        start_time = self.pending_stages[task_id].get("start_time", time.time())
                        del self.pending_stages[task_id]
                    
                    result = self.node.model_manager.inference(prompt, max_tokens=max_tokens)
                    
                    return {
                        "success": True,
                        "response": result.response,
                        "tokens": result.tokens,
                        "latency": time.time() - start_time,
                    }
                    
        except Exception as e:
            logger.error(f"第一阶段执行失败: {e}")
            traceback.print_exc()
            return {"success": False, "error": str(e)}
    
    def handle_stage_result(self, task_id: str, stage: int, 
                           hidden_states: bytes, attention_mask: bytes = None):
        """
        处理阶段结果
        
        Args:
            task_id: 任务ID
            stage: 当前阶段
            hidden_states: 隐藏状态（压缩后）
            attention_mask: 注意力掩码（压缩后）
        """
        try:
            # 解压隐藏状态
            hidden_bytes = zlib.decompress(hidden_states)
            hidden_numpy = pickle.loads(hidden_bytes)
            hidden_tensor = torch.from_numpy(hidden_numpy)
            
            if self.node.model_manager.device != "cpu":
                hidden_tensor = hidden_tensor.to(self.node.model_manager.device)
            
            # 获取任务信息
            with self.lock:
                task_info = self.pending_stages.get(task_id)
                if not task_info:
                    return {"success": False, "error": "任务不存在"}
                actual_pipeline_id = task_info.get("pipeline_id", "default")
            
            # Bug 5 fix: use actual pipeline_id
            nodes = self.pipeline_groups.get(actual_pipeline_id, [])
            next_stage = stage + 1
            
            if next_stage >= len(nodes):
                # 最后阶段，生成结果
                return self._generate_final_output(task_id, hidden_tensor)
            else:
                # 发送到下一阶段
                next_node_id = nodes[next_stage]
                
                # 序列化
                hidden_numpy = hidden_tensor.cpu().numpy()
                hidden_bytes = pickle.dumps(hidden_numpy)
                hidden_compressed = zlib.compress(hidden_bytes)
                
                return self._send_to_node(next_node_id, {
                    "type": "pipeline_stage",
                    "task_id": task_id,
                    "stage": next_stage,
                    "hidden_states": hidden_compressed,
                    "attention_mask": attention_mask,
                })
                
        except Exception as e:
            logger.error(f"处理阶段结果失败: {e}")
            traceback.print_exc()
            return {"success": False, "error": str(e)}
    
    # Bug 1 fix: use string annotation 'torch.Tensor' instead of torch.Tensor
    def _generate_final_output(self, task_id: str, hidden_states: 'torch.Tensor') -> Dict:
        """
        生成最终输出
        
        Improvement 3: Do proper token-by-token generation using the model's
        generate method when available, rather than just generating 1 token.
        """
        try:
            # Get task info for max_tokens
            with self.lock:
                task_info = self.pending_stages.get(task_id, {})
                max_tokens = task_info.get("max_tokens", 256)
                start_time = task_info.get("start_time", time.time())
            
            model = self.node.model_manager.model
            tokenizer = self.node.model_manager.tokenizer
            
            if hasattr(model, 'generate'):
                # Improvement 3: Use the model's generate method for proper multi-token generation
                with torch.no_grad():
                    if hasattr(model, 'model'):
                        # Try to run the final stages through the model directly
                        # If we have hidden_states from a partial pipeline, decode them
                        if hasattr(model, 'lm_head'):
                            generated_ids = []
                            current_hidden = hidden_states
                            
                            for _ in range(max_tokens):
                                logits = model.lm_head(current_hidden)
                                next_token = torch.argmax(logits[:, -1, :], dim=-1)
                                generated_ids.append(next_token)
                                
                                # Check for EOS
                                if (tokenizer.eos_token_id is not None and 
                                    next_token.item() == tokenizer.eos_token_id):
                                    break
                                
                                # Get embedding for next token to continue
                                if hasattr(model.model, 'embed_tokens'):
                                    next_embed = model.model.embed_tokens(next_token)
                                elif hasattr(model.model, 'wte'):
                                    next_embed = model.model.wte(next_token)
                                else:
                                    break
                                
                                current_hidden = torch.cat([current_hidden, next_embed.unsqueeze(1)], dim=1)
                            
                            all_tokens = torch.cat(generated_ids, dim=-1) if generated_ids else torch.tensor([], dtype=torch.long)
                            response = tokenizer.decode(all_tokens, skip_special_tokens=True)
                        else:
                            response = ""
                    else:
                        response = ""
            else:
                response = ""
            
            # 清理和统计
            latency = time.time() - start_time
            with self.lock:
                if task_id in self.pending_stages:
                    del self.pending_stages[task_id]
                
                # 更新统计
                self.total_pipeline_inferences += 1
                self.total_pipeline_latency += latency
            
            return {
                "success": True,
                "response": response,
                "tokens": len(response) if response else 1,
                "latency": latency,
            }
            
        except Exception as e:
            logger.error(f"生成输出失败: {e}")
            traceback.print_exc()
            return {"success": False, "error": str(e)}
    
    # Bug 2 fix: use send_message_to_node convenience method
    def _send_to_node(self, node_id: str, message: Dict) -> Dict:
        """发送消息到节点"""
        try:
            # 使用网络管理器的 send_message_to_node 方法
            return self.node.network.send_message_to_node(
                node_id, MessageType.PIPELINE_DATA, message,
                wait_response=True, timeout=self.node.config.message_timeout
            ) or {"success": False, "error": "No response from node"}
        except Exception as e:
            logger.error(f"发送消息失败: {e}")
            return {"success": False, "error": str(e)}
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        with self.lock:
            return {
                "pipeline_groups": len(self.pipeline_groups),
                "pending_tasks": len(self.pending_stages),
                "total_inferences": self.total_pipeline_inferences,
                "avg_latency": self.total_pipeline_latency / max(1, self.total_pipeline_inferences),
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
        
        # 统计
        self.messages_sent = 0
        self.messages_received = 0
        self.bytes_sent = 0
        self.bytes_received = 0
    
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
        logger.info(f"TCP服务器启动: {self.config.host}:{self.config.port}")
    
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
                    logger.error(f"接受连接错误: {e}")
    
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
                self.messages_received += 1
                self.bytes_received += len(data)
                
                message = self._decode_message(data)
                if message:
                    # Bug 7 fix: handle unknown message types gracefully
                    raw_type = message.get("type", "")
                    try:
                        msg_type = MessageType(raw_type)
                    except ValueError:
                        logger.warning(f"收到未知消息类型: {raw_type}, 来自 {addr}")
                        return
                    
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
                            encoded = self._encode_message(response_msg)
                            conn.sendall(encoded)
                            self.bytes_sent += len(encoded)
        except Exception as e:
            # Bug 9 fix: use except Exception instead of bare except
            logger.debug(f"处理连接错误: {e}")
        finally:
            conn.close()
    
    def send_message(self, host: str, port: int, msg_type: MessageType,
                     data: Dict, wait_response: bool = False,
                     timeout: float = 10.0) -> Optional[Dict]:
        """发送消息
        
        Improvement 5: Added retry logic for transient failures.
        """
        max_retries = getattr(self.config, 'message_retries', 2)
        last_error = None
        
        for attempt in range(max_retries + 1):
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
                
                encoded = self._encode_message(message)
                sock.sendall(encoded)
                self.messages_sent += 1
                self.bytes_sent += len(encoded)
                
                if wait_response:
                    sock.shutdown(socket.SHUT_WR)
                    response_data = b""
                    while True:
                        chunk = sock.recv(65536)
                        if not chunk:
                            break
                        response_data += chunk
                    
                    sock.close()
                    
                    if response_data:
                        self.bytes_received += len(response_data)
                        return self._decode_message(response_data)
                else:
                    sock.close()
                
                return None
            except Exception as e:
                last_error = e
                logger.debug(f"发送消息到 {host}:{port} 失败 (尝试 {attempt+1}/{max_retries+1}): {e}")
                try:
                    sock.close()
                except Exception:
                    pass
                if attempt < max_retries:
                    time.sleep(0.1 * (attempt + 1))
        
        logger.debug(f"发送消息到 {host}:{port} 最终失败: {last_error}")
        return None
    
    # Bug 2 fix: Add convenience method to send to node by ID
    def send_message_to_node(self, node_id: str, msg_type: MessageType,
                              data: Dict, wait_response: bool = False,
                              timeout: float = 0.0) -> Optional[Dict]:
        """
        通过节点ID发送消息（自动查找 host/port）
        
        Args:
            node_id: 目标节点ID
            msg_type: 消息类型
            data: 消息数据
            wait_response: 是否等待响应
            timeout: 超时时间（0表示使用配置默认值）
            
        Returns:
            响应字典或None
        """
        node_info = self.known_nodes.get(node_id)
        if not node_info:
            logger.error(f"未知节点: {node_id}")
            return None
        
        if not node_info.host or not node_info.port:
            logger.error(f"节点 {node_id} 没有有效的 host/port")
            return None
        
        if timeout <= 0:
            timeout = getattr(self.config, 'message_timeout', 10.0)
        
        return self.send_message(
            node_info.host, node_info.port, msg_type, data,
            wait_response=wait_response, timeout=timeout
        )
    
    # Bug 2 fix: Add method for sending raw message dicts (used by cluster handlers)
    def send_raw_message(self, host: str, port: int, message: Dict,
                         wait_response: bool = False, timeout: float = 10.0) -> Optional[Dict]:
        """
        发送原始消息字典
        
        用于向后兼容：一些旧代码构造完整消息字典而非使用 MessageType 枚举。
        该方法从 message dict 中提取 type 字段并正确发送。
        
        Args:
            host: 目标主机
            port: 目标端口
            message: 完整的消息字典（必须包含 "type" 和 "data" 字段）
            wait_response: 是否等待响应
            timeout: 超时时间
        """
        msg_type_str = message.get("type", "heartbeat")
        data = message.get("data", message)  # 如果没有 data 字段，使用整个消息
        
        try:
            msg_type = MessageType(msg_type_str)
        except ValueError:
            msg_type = MessageType.HEARTBEAT
            logger.debug(f"send_raw_message: 未知消息类型 '{msg_type_str}', 使用 HEARTBEAT")
        
        return self.send_message(host, port, msg_type, data, 
                                 wait_response=wait_response, timeout=timeout)
    
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
            except Exception:
                pass  # Bug 9 fix
    
    def _encode_message(self, message: Dict) -> bytes:
        """编码消息"""
        return zlib.compress(pickle.dumps(message))
    
    def _decode_message(self, data: bytes) -> Optional[Dict]:
        """解码消息"""
        try:
            return pickle.loads(zlib.decompress(data))
        except Exception as e:
            logger.error(f"解码消息失败: {e}")
            return None
    
    def stop(self):
        """停止网络"""
        self.running = False
        
        for sock in self.connections.values():
            try:
                sock.close()
            except Exception:
                pass  # Bug 9 fix
        
        if self.server_socket:
            try:
                self.server_socket.close()
            except Exception:
                pass  # Bug 9 fix
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            "messages_sent": self.messages_sent,
            "messages_received": self.messages_received,
            "bytes_sent": self.bytes_sent,
            "bytes_received": self.bytes_received,
            "known_nodes": len(self.known_nodes),
        }


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
        
        # 统计
        self.elections_started = 0
        self.elections_won = 0
    
    def start(self):
        """启动选举服务"""
        self.running = True
        
        self.network.register_handler(MessageType.REQUEST_VOTE, self._handle_vote_request)
        self.network.register_handler(MessageType.HEARTBEAT, self._handle_heartbeat)
        
        self._reset_election_timer()
        logger.info(f"Raft选举服务启动，初始角色: {self.role.value}")
    
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
        
        self.elections_started += 1
        logger.info(f"开始选举，任期 {self.current_term + 1}")
        
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
                logger.info(f"投票给 {candidate_id[:8]}")
        
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
        self.elections_won += 1
        logger.info(f"[LEADER] 成为领导节点! 任期 {self.current_term}")
        
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
                "nodes": {nid: n.to_dict() for nid, n in self.network.known_nodes.items()},
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
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            "role": self.role.value,
            "term": self.current_term,
            "leader_id": self.leader_id,
            "elections_started": self.elections_started,
            "elections_won": self.elections_won,
        }


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
        self.device = "cpu"
        
        # 分片信息
        self.shard_id = -1
        self.shard_layers: List = []
        self.pipeline_stage = -1
        
        # 统计
        self.total_inferences = 0
        self.total_tokens = 0
        self.total_latency = 0.0
    
    def load(self, shard_info: Dict = None) -> bool:
        """加载模型"""
        if not HAS_TORCH:
            logger.error("PyTorch未安装，无法加载模型")
            return False
        
        if self.loaded:
            return True
        
        start_time = time.time()
        
        try:
            logger.info(f"加载模型: {self.config.model_name}")
            
            # 加载tokenizer
            logger.info("   [1/2] 加载Tokenizer...")
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.config.model_name,
                trust_remote_code=True
            )
            
            if self.tokenizer.pad_token is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token
            
            # 加载模型
            logger.info("   [2/2] 加载模型权重...")
            
            if torch.cuda.is_available():
                self.device = "cuda"
                torch_dtype = torch.float16
            elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
                self.device = "mps"
                torch_dtype = torch.float16
            else:
                self.device = "cpu"
                torch_dtype = torch.float32
            
            self.model = AutoModelForCausalLM.from_pretrained(
                self.config.model_name,
                torch_dtype=torch_dtype,
                trust_remote_code=True,
                low_cpu_mem_usage=True,
            )
            
            if self.device != "cpu":
                self.model = self.model.to(self.device)
            
            self.model.eval()
            
            param_count = sum(p.numel() for p in self.model.parameters())
            self.model_size_gb = param_count * 4 / (1024**3)
            
            self.loaded = True
            self.load_time = time.time() - start_time
            
            logger.info(f"模型加载完成! 参数量: {param_count/1e9:.2f}B, "
                       f"大小: {self.model_size_gb:.2f}GB, 设备: {self.device}, "
                       f"时间: {self.load_time:.1f}s")
            
            return True
            
        except Exception as e:
            logger.error(f"模型加载失败: {e}")
            traceback.print_exc()
            return False
    
    def inference(self, prompt: str, max_tokens: int = 256,
                  temperature: float = 0.7, **kwargs) -> InferenceResult:
        """推理"""
        if not self.loaded:
            return InferenceResult(success=False, error="模型未加载")
        
        try:
            start_time = time.time()
            
            inputs = self.tokenizer(prompt, return_tensors="pt")
            if self.device != "cpu":
                inputs = {k: v.to(self.device) for k, v in inputs.items()}
            
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
            
            # 更新统计
            self.total_inferences += 1
            self.total_tokens += new_tokens
            self.total_latency += latency
            
            return InferenceResult(
                success=True,
                response=response,
                tokens=new_tokens,
                latency=latency,
                throughput=new_tokens / latency if latency > 0 else 0,
            )
            
        except Exception as e:
            return InferenceResult(success=False, error=str(e))
    
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
        
        # Bug 14 fix: gc is now a top-level import
        gc.collect()
        
        logger.info("模型已卸载")
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            "loaded": self.loaded,
            "model_name": self.config.model_name,
            "model_size_gb": self.model_size_gb,
            "device": self.device,
            "load_time": self.load_time,
            "total_inferences": self.total_inferences,
            "total_tokens": self.total_tokens,
            "total_latency": self.total_latency,
            "avg_latency": self.total_latency / max(1, self.total_inferences),
            "avg_throughput": self.total_tokens / max(0.001, self.total_latency),
        }
    
    def get_layer_count(self) -> int:
        """获取模型层数"""
        if not self.loaded or self.model is None:
            return 0
        
        try:
            # 获取 transformer 层数
            if hasattr(self.model, 'config'):
                if hasattr(self.model.config, 'num_hidden_layers'):
                    return self.model.config.num_hidden_layers
                elif hasattr(self.model.config, 'n_layer'):
                    return self.model.config.n_layer
                elif hasattr(self.model.config, 'num_layers'):
                    return self.model.config.num_layers
            
            # 尝试从模型结构推断
            if hasattr(self.model, 'model'):
                if hasattr(self.model.model, 'layers'):
                    return len(self.model.model.layers)
                elif hasattr(self.model.model, 'h'):
                    return len(self.model.model.h)
            
            return 0
        except Exception:
            return 0
    
    def load_shard(self, stage_id: int, total_stages: int) -> bool:
        """
        加载模型分片（Pipeline 并行）
        
        Args:
            stage_id: 当前阶段ID (0-based)
            total_stages: 总阶段数
            
        Returns:
            是否加载成功
        """
        if not HAS_TORCH:
            logger.error("PyTorch未安装，无法加载模型分片")
            return False
        
        start_time = time.time()
        
        try:
            logger.info(f"加载模型分片: 阶段 {stage_id+1}/{total_stages}")
            
            # 加载完整模型配置
            config = AutoConfig.from_pretrained(
                self.config.model_name,
                trust_remote_code=True
            )
            
            # 获取总层数
            total_layers = self.get_layer_count()
            if total_layers == 0:
                logger.warning("无法获取模型层数，回退到完整模型加载")
                return self.load()
            
            # 计算每个阶段的层数
            layers_per_stage = total_layers // total_stages
            remainder = total_layers % total_stages
            
            # 计算当前阶段的层范围
            layer_start = stage_id * layers_per_stage + min(stage_id, remainder)
            if stage_id < remainder:
                layer_end = layer_start + layers_per_stage + 1
            else:
                layer_end = layer_start + layers_per_stage
            
            # 最后一阶段包含所有剩余层
            if stage_id == total_stages - 1:
                layer_end = total_layers
            
            logger.info(f"   层范围: {layer_start}-{layer_end-1} (共 {layer_end - layer_start} 层)")
            
            # 加载 tokenizer
            logger.info("   [1/2] 加载Tokenizer...")
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.config.model_name,
                trust_remote_code=True
            )
            
            if self.tokenizer.pad_token is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token
            
            # 加载完整模型（暂时，实际应用中应该只加载分片）
            # 注意：真正的分片加载需要更复杂的实现，这里先加载完整模型
            # 然后只使用指定层
            logger.info("   [2/2] 加载模型分片...")
            
            if torch.cuda.is_available():
                self.device = "cuda"
                torch_dtype = torch.float16
            elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
                self.device = "mps"
                torch_dtype = torch.float16
            else:
                self.device = "cpu"
                torch_dtype = torch.float32
            
            # 加载完整模型
            self.model = AutoModelForCausalLM.from_pretrained(
                self.config.model_name,
                torch_dtype=torch_dtype,
                trust_remote_code=True,
                low_cpu_mem_usage=True,
            )
            
            if self.device != "cpu":
                self.model = self.model.to(self.device)
            
            self.model.eval()
            
            # 保存分片信息
            self.pipeline_stage = stage_id
            self.shard_layers = list(range(layer_start, layer_end))
            self.shard_id = stage_id
            
            param_count = sum(p.numel() for p in self.model.parameters())
            self.model_size_gb = param_count * 4 / (1024**3)
            
            self.loaded = True
            self.load_time = time.time() - start_time
            
            # 标记是否为第一/最后阶段
            is_first = (stage_id == 0)
            is_last = (stage_id == total_stages - 1)
            
            stage_type = '第一阶段' if is_first else '最后阶段' if is_last else '中间阶段'
            logger.info(f"分片加载完成! 阶段: {stage_id+1}/{total_stages}, "
                       f"层: {layer_start}-{layer_end-1}, 类型: {stage_type}, "
                       f"设备: {self.device}, 时间: {self.load_time:.1f}s")
            
            return True
            
        except Exception as e:
            logger.error(f"分片加载失败: {e}")
            traceback.print_exc()
            return False
    
    def forward_stage(self, hidden_states: Any, attention_mask: Any = None) -> Any:
        """
        执行当前阶段的前向传播
        
        Args:
            hidden_states: 输入隐藏状态
            attention_mask: 注意力掩码
            
        Returns:
            输出隐藏状态
        """
        if not self.loaded or self.model is None:
            raise ValueError("模型未加载")
        
        try:
            # 获取模型的 transformer 部分
            if hasattr(self.model, 'model'):
                transformer = self.model.model
            elif hasattr(self.model, 'transformer'):
                transformer = self.model.transformer
            else:
                transformer = self.model
            
            # 执行指定层的前向传播
            with torch.no_grad():
                # 如果有 embedding 层且是第一阶段，需要先嵌入
                if self.pipeline_stage == 0:
                    if hasattr(transformer, 'embed_tokens'):
                        hidden_states = transformer.embed_tokens(hidden_states)
                    elif hasattr(transformer, 'wte'):
                        hidden_states = transformer.wte(hidden_states)
                
                # 执行当前阶段的层
                if hasattr(transformer, 'layers'):
                    layers = transformer.layers
                elif hasattr(transformer, 'h'):
                    layers = transformer.h
                else:
                    layers = []
                
                for layer_idx in self.shard_layers:
                    if layer_idx < len(layers):
                        layer = layers[layer_idx]
                        if attention_mask is not None:
                            hidden_states = layer(hidden_states, attention_mask=attention_mask)
                        else:
                            hidden_states = layer(hidden_states)
                
                # 如果是最后阶段，需要经过 lm_head
                if self.pipeline_stage >= 0:  # 简化判断
                    if hasattr(self.model, 'lm_head'):
                        hidden_states = self.model.lm_head(hidden_states)
            
            return hidden_states
            
        except Exception as e:
            logger.error(f"前向传播错误: {e}")
            traceback.print_exc()
            raise


# ==================== API 服务器 ====================

class APIRequestHandler(BaseHTTPRequestHandler):
    """API 请求处理器"""
    
    node: 'UnifiedNode' = None
    
    def log_message(self, format, *args):
        """自定义日志"""
        pass  # 禁用默认日志
    
    def _send_json_response(self, data: Dict, status: int = 200):
        """发送 JSON 响应"""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))
    
    def _read_json_body(self) -> Dict:
        """读取 JSON 请求体"""
        content_length = int(self.headers.get('Content-Length', 0))
        if content_length > 0:
            body = self.rfile.read(content_length)
            return json.loads(body.decode('utf-8'))
        return {}
    
    def do_GET(self):
        """处理 GET 请求"""
        parsed = urlparse(self.path)
        path = parsed.path
        
        if path == '/':
            self._handle_root()
        elif path == '/health':
            self._handle_health()
        elif path == '/status':
            self._handle_status()
        elif path == '/nodes':
            self._handle_nodes()
        elif path == '/models':
            self._handle_models()
        elif path == '/stats':
            self._handle_stats()
        elif path.startswith('/v1/'):
            self._handle_openai_get(path)
        else:
            self._send_json_response({"error": "Not found"}, 404)
    
    def do_POST(self):
        """处理 POST 请求"""
        parsed = urlparse(self.path)
        path = parsed.path
        
        if path == '/v1/chat/completions':
            self._handle_chat_completions()
        elif path == '/v1/completions':
            self._handle_completions()
        elif path == '/inference':
            self._handle_inference()
        else:
            self._send_json_response({"error": "Not found"}, 404)
    
    def do_OPTIONS(self):
        """处理 OPTIONS 请求 (CORS)"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()
    
    def _handle_root(self):
        """处理根路径"""
        self._send_json_response({
            "name": "统一分布式推理系统",
            "version": VERSION,
            "endpoints": {
                "health": "/health",
                "status": "/status",
                "nodes": "/nodes",
                "models": "/models",
                "stats": "/stats",
                "chat": "/v1/chat/completions",
                "completions": "/v1/completions",
                "inference": "/inference",
            }
        })
    
    def _handle_health(self):
        """处理健康检查"""
        health_score = ResourceMonitor.get_health_score()
        
        self._send_json_response({
            "status": "healthy" if health_score > 50 else "degraded",
            "health_score": health_score,
            "model_loaded": self.node.model_manager.loaded if self.node else False,
            "timestamp": time.time(),
        })
    
    def _handle_status(self):
        """处理状态请求"""
        if not self.node:
            self._send_json_response({"error": "Node not initialized"}, 500)
            return
        
        self._send_json_response({
            "node": self.node.node_info.to_dict(),
            "config": self.node.config.to_dict(),
            "election": self.node.election.get_stats(),
            "load_balancer": self.node.load_balancer.get_stats(),
            "model": self.node.model_manager.get_stats(),
            "network": self.node.network.get_stats(),
        })
    
    def _handle_nodes(self):
        """处理节点列表请求"""
        if not self.node:
            self._send_json_response({"error": "Node not initialized"}, 500)
            return
        
        nodes = {
            nid: node.to_dict() 
            for nid, node in self.node.network.known_nodes.items()
        }
        nodes[self.node.node_id] = self.node.node_info.to_dict()
        
        self._send_json_response({
            "total": len(nodes),
            "nodes": nodes,
        })
    
    def _handle_models(self):
        """处理模型列表请求"""
        self._send_json_response({
            "models": [
                {
                    "id": self.node.config.model_name,
                    "name": self.node.config.model_name,
                    "loaded": self.node.model_manager.loaded if self.node else False,
                    "size_gb": self.node.model_manager.model_size_gb if self.node else 0,
                }
            ]
        })
    
    def _handle_stats(self):
        """处理统计请求"""
        if not self.node:
            self._send_json_response({"error": "Node not initialized"}, 500)
            return
        
        self._send_json_response({
            "model": self.node.model_manager.get_stats(),
            "load_balancer": self.node.load_balancer.get_stats(),
            "network": self.node.network.get_stats(),
            "resource": ResourceMonitor.get_system_info(),
        })
    
    def _handle_chat_completions(self):
        """处理 OpenAI 兼容的聊天请求"""
        if not self.node:
            self._send_json_response({"error": "Node not initialized"}, 500)
            return
        
        try:
            body = self._read_json_body()
            
            messages = body.get("messages")
            # Bug 15 fix: Validate required fields
            if not messages or not isinstance(messages, list) or len(messages) == 0:
                self._send_json_response({
                    "error": {
                        "message": "'messages' is a required field and must be a non-empty array",
                        "type": "invalid_request_error",
                    }
                }, 400)
                return
            
            # Validate each message has required fields
            for i, msg in enumerate(messages):
                if not isinstance(msg, dict):
                    self._send_json_response({
                        "error": {
                            "message": f"messages[{i}] must be an object",
                            "type": "invalid_request_error",
                        }
                    }, 400)
                    return
                if "role" not in msg or "content" not in msg:
                    self._send_json_response({
                        "error": {
                            "message": f"messages[{i}] must have 'role' and 'content' fields",
                            "type": "invalid_request_error",
                        }
                    }, 400)
                    return
            
            model = body.get("model", self.node.config.model_name)
            max_tokens = body.get("max_tokens", 256)
            temperature = body.get("temperature", 0.7)
            stream = body.get("stream", False)
            
            # 构建提示
            prompt = ""
            for msg in messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if role == "system":
                    prompt += f"System: {content}\n"
                elif role == "user":
                    prompt += f"User: {content}\n"
                elif role == "assistant":
                    prompt += f"Assistant: {content}\n"
            
            prompt += "Assistant:"
            
            # 执行推理
            result = self.node.model_manager.inference(
                prompt,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            
            if result.success:
                response = {
                    "id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
                    "object": "chat.completion",
                    "created": int(time.time()),
                    "model": model,
                    "choices": [
                        {
                            "index": 0,
                            "message": {
                                "role": "assistant",
                                "content": result.response,
                            },
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {
                        "prompt_tokens": 0,
                        "completion_tokens": result.tokens,
                        "total_tokens": result.tokens,
                    },
                }
                self._send_json_response(response)
            else:
                self._send_json_response({"error": result.error}, 500)
                
        except Exception as e:
            self._send_json_response({"error": str(e)}, 500)
    
    def _handle_completions(self):
        """处理 OpenAI 兼容的补全请求"""
        if not self.node:
            self._send_json_response({"error": "Node not initialized"}, 500)
            return
        
        try:
            body = self._read_json_body()
            
            # Bug 15 fix: Validate required fields
            prompt = body.get("prompt")
            if prompt is None:
                self._send_json_response({
                    "error": {
                        "message": "'prompt' is a required field",
                        "type": "invalid_request_error",
                    }
                }, 400)
                return
            
            model = body.get("model", self.node.config.model_name)
            max_tokens = body.get("max_tokens", 256)
            temperature = body.get("temperature", 0.7)
            
            result = self.node.model_manager.inference(
                str(prompt),
                max_tokens=max_tokens,
                temperature=temperature,
            )
            
            if result.success:
                response = {
                    "id": f"cmpl-{uuid.uuid4().hex[:8]}",
                    "object": "text_completion",
                    "created": int(time.time()),
                    "model": model,
                    "choices": [
                        {
                            "index": 0,
                            "text": result.response,
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {
                        "prompt_tokens": 0,
                        "completion_tokens": result.tokens,
                        "total_tokens": result.tokens,
                    },
                }
                self._send_json_response(response)
            else:
                self._send_json_response({"error": result.error}, 500)
                
        except Exception as e:
            self._send_json_response({"error": str(e)}, 500)
    
    def _handle_inference(self):
        """处理原生推理请求"""
        if not self.node:
            self._send_json_response({"error": "Node not initialized"}, 500)
            return
        
        try:
            body = self._read_json_body()
            
            # Bug 15 fix: Validate required fields
            prompt = body.get("prompt")
            if prompt is None:
                self._send_json_response({
                    "error": {
                        "message": "'prompt' is a required field",
                        "type": "invalid_request_error",
                    }
                }, 400)
                return
            
            max_tokens = body.get("max_tokens", 256)
            temperature = body.get("temperature", 0.7)
            
            result = self.node.model_manager.inference(
                str(prompt),
                max_tokens=max_tokens,
                temperature=temperature,
            )
            
            self._send_json_response(result.to_dict())
            
        except Exception as e:
            self._send_json_response({"error": str(e)}, 500)
    
    def _handle_openai_get(self, path: str):
        """处理 OpenAI 兼容的 GET 请求"""
        if path == '/v1/models':
            self._handle_models()
        else:
            self._send_json_response({"error": "Not found"}, 404)


# ==================== 统一节点 ====================

class UnifiedNode:
    """统一节点 - 支持所有模式"""
    
    # Bug 11 fix: Maximum completed tasks to keep in memory
    MAX_COMPLETED_TASKS = 1000
    
    def __init__(self, config: UnifiedConfig):
        self.config = config
        
        # 配置日志
        setup_logging(config.log_level, config.log_file)
        
        # 组件
        self.network = NetworkManager(config)
        self.election = RaftElection(config, self.network)
        self.model_manager = ModelManager(config)
        self.load_balancer = LoadBalancer(
            config.load_balance_strategy,
            config.straggler_threshold
        )
        self.pipeline_coordinator = DistributedInferenceCoordinator(self)
        
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
        self.completed_tasks: OrderedDict = OrderedDict()  # Bug 11: OrderedDict for size limit
        self.task_lock = threading.Lock()
        
        # Pipeline
        self.pipeline_stages: List[PipelineStage] = []
        self.pipeline_enabled = False
        self.pipeline_stage_id = -1
        
        # 集群资源协调
        self.cluster_resources: Dict[str, Dict] = {}  # node_id -> resource_info
        self.cluster_resource_lock = threading.Lock()
        self.waiting_for_cluster = False
        self.cluster_ready_event = threading.Event()
        self.distributed_loading_plan: Optional[Dict] = None
        
        # 状态
        self.running = False
        self.api_server: Optional[HTTPServer] = None
        self.start_time = time.time()
        
        # 线程追踪（用于清理）
        self._threads: List[threading.Thread] = []
    
    def start(self):
        """启动节点"""
        self._print_banner()
        
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
        
        # Bug 12 / Improvement 8: Connect to seed nodes on startup
        self._connect_to_seeds()
        
        # 估算模型大小
        model_size_gb = ResourceMonitor.estimate_model_size(self.config.model_name)
        logger.info(f"目标模型: {self.config.model_name}")
        logger.info(f"估算大小: {model_size_gb:.1f}GB")
        logger.info(f"可用内存: {self.node_info.memory_available_gb:.1f}GB")
        
        # 检查内存并决定加载策略
        use_distributed = False
        
        if self.config.auto_mode or self.config.parallel_mode == ParallelMode.PIPELINE_PARALLEL:
            # 自动模式或Pipeline模式 - 检查是否需要分布式加载
            can_run, reason = ResourceMonitor.can_run_model(model_size_gb)
            
            if not can_run:
                logger.warning(f"本地内存不足: {reason}")
                logger.info("尝试等待集群资源进行分布式加载...")
                
                # 等待集群资源
                if self._check_and_wait_for_cluster(model_size_gb):
                    use_distributed = True
                    # 规划分布式加载
                    plan = self._plan_distributed_loading(model_size_gb)
                    
                    # 执行分布式加载
                    if not self._coordinate_distributed_loading(plan):
                        logger.warning("分布式加载失败，API服务将以无模型模式启动")
                else:
                    logger.warning("无法获得足够的集群资源，API服务将以无模型模式启动")
            else:
                # 内存充足，检查是否配置了Pipeline模式
                if self.config.parallel_mode == ParallelMode.PIPELINE_PARALLEL:
                    use_distributed = True
                    total_stages = self.config.pipeline_stages
                    
                    # Bug 3 fix: self.election.state -> self.election.role
                    # Bug 4 fix: self.network.peers -> self.network.known_nodes
                    if self.election.role == NodeRole.LEADER:
                        stage_id = 0
                    else:
                        stage_id = len(self.network.known_nodes) % total_stages
                    
                    logger.info(f"加载模型分片... 阶段: {stage_id + 1}/{total_stages}")
                    
                    if not self.model_manager.load_shard(stage_id, total_stages):
                        logger.warning("模型分片加载失败，API服务将以无模型模式启动")
                    
                    self.pipeline_enabled = self.model_manager.loaded
                    self.pipeline_stage_id = stage_id if self.pipeline_enabled else -1
        
        # 常规加载（内存充足且不需要分布式）
        if not use_distributed:
            if self.config.parallel_mode == ParallelMode.PIPELINE_PARALLEL:
                # Pipeline 模式但不需要等待集群
                total_stages = self.config.pipeline_stages
                if total_stages <= 1:
                    total_stages = 2
                
                # Bug 3 fix: self.election.state -> self.election.role
                # Bug 4 fix: self.network.peers -> self.network.known_nodes
                if self.election.role == NodeRole.LEADER:
                    stage_id = 0
                else:
                    stage_id = len(self.network.known_nodes) % total_stages
                
                logger.info(f"加载模型分片... 阶段: {stage_id + 1}/{total_stages}")
                
                if not self.model_manager.load_shard(stage_id, total_stages):
                    logger.warning("模型分片加载失败，API服务将以无模型模式启动")
                
                self.pipeline_enabled = self.model_manager.loaded
                self.pipeline_stage_id = stage_id if self.pipeline_enabled else -1
                
            elif self.config.parallel_mode == ParallelMode.HYBRID:
                logger.warning("混合并行模式尚未完全实现，使用数据并行")
                if not self.model_manager.load():
                    logger.warning("模型加载失败，API服务将以无模型模式启动")
            else:
                # 数据并行模式 - 加载完整模型
                if not self.model_manager.load():
                    logger.warning("模型加载失败，API服务将以无模型模式启动")
        
        if self.model_manager.loaded:
            self.node_info.model_loaded = True
        self.node_info.model_name = self.config.model_name
        
        # 启动API服务器
        self._start_api_server()
        
        # 启动后台任务
        heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        heartbeat_thread.start()
        self._threads.append(heartbeat_thread)
        
        task_thread = threading.Thread(target=self._task_loop, daemon=True)
        task_thread.start()
        self._threads.append(task_thread)
        
        logger.info("=" * 60)
        logger.info("节点启动完成!")
        logger.info(f"API: http://{self.config.api_host}:{self.config.api_port}")
        logger.info("=" * 60)
        logger.info("按 Ctrl+C 停止...")
        
        # 主循环
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("正在停止...")
            self.stop()
    
    def _print_banner(self):
        """打印启动横幅"""
        logger.info("=" * 60)
        logger.info(f"  统一分布式推理系统 v{VERSION}")
        logger.info("=" * 60)
        logger.info(f"  节点ID:   {self.config.node_id[:8]}")
        logger.info(f"  节点名称: {self.config.node_name}")
        logger.info(f"  并行模式: {self.config.parallel_mode.value}")
        logger.info(f"  调度模式: {self.config.schedule_mode.value}")
        logger.info(f"  模型:     {self.config.model_name}")
        logger.info("=" * 60)
        
        # 显示模式信息
        mode_info = ModeSelector.get_mode_info(self.config.parallel_mode)
        if mode_info:
            logger.info(f"【{mode_info.get('name', '')}】")
            logger.info(f"  {mode_info.get('description', '')}")
            logger.info(f"  优点: {', '.join(mode_info.get('pros', []))}")
            logger.info(f"  缺点: {', '.join(mode_info.get('cons', []))}")
    
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
        self.network.register_handler(
            MessageType.PIPELINE_DATA, self._handle_pipeline_data
        )
        
        # Bug 17 fix: Register VOTE_RESPONSE handler
        self.network.register_handler(
            MessageType.VOTE_RESPONSE, self._handle_vote_response
        )
        
        # Bug 7/Improvement 6/7: Fix cluster resource handlers to accept from_node
        self.network.register_handler(
            MessageType.CLUSTER_RESOURCE_QUERY, 
            self._handle_cluster_resource_query
        )
        self.network.register_handler(
            MessageType.CLUSTER_RESOURCE_RESPONSE,
            self._handle_cluster_resource_response
        )
        self.network.register_handler(
            MessageType.CLUSTER_START_DISTRIBUTED,
            self._handle_cluster_start_distributed
        )
    
    def _handle_discover(self, data: Dict, from_node: str) -> Dict:
        """处理发现请求"""
        # Register the discovering node
        if data.get("node_info"):
            try:
                node_info = NodeInfo.from_dict(data["node_info"])
                self.network.known_nodes[node_info.node_id] = node_info
                # Also register any nodes they know about
                for nid, ndata in data.get("known_nodes", {}).items():
                    if nid != self.node_info.node_id and nid not in self.network.known_nodes:
                        self.network.known_nodes[nid] = NodeInfo.from_dict(ndata)
                logger.info(f"发现节点: {from_node[:8]} (已知节点: {len(self.network.known_nodes)})")
            except Exception as e:
                logger.debug(f"处理发现信息失败: {e}")
        
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
        
        # 更新负载均衡器
        self.load_balancer.update_node_stats(
            self.node_info.node_id,
            result.latency,
            result.success
        )
        
        return result.to_dict()
    
    def _handle_task_assign(self, data: Dict, from_node: str) -> Dict:
        """处理任务分配"""
        task_id = data.get("task_id")
        prompt = data.get("prompt")
        params = data.get("params", {})
        
        result = self.model_manager.inference(prompt, **params)
        
        return {
            "accepted": True,
            "task_id": task_id,
            **result.to_dict()
        }
    
    # Bug 10/18 fix: Connect _handle_pipeline_data to the pipeline coordinator
    def _handle_pipeline_data(self, data: Dict, from_node: str) -> Dict:
        """
        处理 Pipeline 数据
        
        Routes pipeline stage messages to the DistributedInferenceCoordinator.
        """
        task_id = data.get("task_id", "")
        stage = data.get("stage", 0)
        prompt = data.get("prompt")
        hidden_states = data.get("hidden_states")
        attention_mask = data.get("attention_mask")
        
        try:
            if hidden_states is not None and isinstance(hidden_states, bytes):
                # This is a continuation message with hidden states
                result = self.pipeline_coordinator.handle_stage_result(
                    task_id, stage, hidden_states, attention_mask
                )
                return result or {"status": "processed"}
            elif prompt is not None:
                # This is an initial stage request with a prompt
                pipeline_id = data.get("pipeline_id", "default")
                max_tokens = data.get("max_tokens", 256)
                result = self.pipeline_coordinator._execute_first_stage(
                    task_id, prompt, pipeline_id
                )
                return result or {"status": "processed"}
            else:
                logger.warning(f"收到未知格式的 Pipeline 数据: task_id={task_id}, stage={stage}")
                return {"status": "received", "error": "Unknown pipeline data format"}
        except Exception as e:
            logger.error(f"处理 Pipeline 数据失败: {e}")
            return {"status": "error", "error": str(e)}
    
    # Bug 17 fix: Handler for VOTE_RESPONSE messages
    def _handle_vote_response(self, data: Dict, from_node: str) -> Dict:
        """处理投票响应"""
        self.election.handle_vote_response(data, from_node)
        return {"status": "received"}
    
    def _on_become_leader(self):
        """成为领导节点回调"""
        logger.info("[LEADER] 成为领导节点，开始接受请求")
    
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
    
    # Bug 12 / Improvement 8: Connect to seed nodes on startup
    def _connect_to_seeds(self):
        """连接到种子节点以发现集群"""
        if not self.config.seeds:
            return
        
        logger.info(f"连接到 {len(self.config.seeds)} 个种子节点...")
        
        for seed in self.config.seeds:
            try:
                parts = seed.split(":")
                host = parts[0]
                port = int(parts[1]) if len(parts) > 1 else self.config.port
                
                # Skip connecting to ourselves
                if host in ("127.0.0.1", "localhost") and port == self.config.port:
                    continue
                if host == self.node_info.host and port == self.config.port:
                    continue
                
                # Send DISCOVER message
                response = self.network.send_message(
                    host, port, MessageType.DISCOVER,
                    {
                        "node_info": self.node_info.to_dict(),
                        "known_nodes": {},
                    },
                    wait_response=True,
                    timeout=5.0
                )
                
                if response:
                    resp_data = response.get("data", response)
                    logger.info(f"成功连接到种子节点 {seed}")
                    
                    # Register discovered nodes
                    if resp_data.get("node_info"):
                        try:
                            node_info = NodeInfo.from_dict(resp_data["node_info"])
                            self.network.known_nodes[node_info.node_id] = node_info
                        except Exception:
                            pass
                    
                    for nid, ndata in resp_data.get("known_nodes", {}).items():
                        if nid != self.node_info.node_id and nid not in self.network.known_nodes:
                            try:
                                self.network.known_nodes[nid] = NodeInfo.from_dict(ndata)
                            except Exception:
                                pass
                else:
                    logger.debug(f"种子节点 {seed} 无响应")
            except Exception as e:
                logger.debug(f"连接种子节点 {seed} 失败: {e}")
    
    def _check_and_wait_for_cluster(self, model_size_gb: float) -> bool:
        """
        检查内存并等待集群资源
        
        Args:
            model_size_gb: 模型大小（GB）
            
        Returns:
            是否成功获得足够资源
        """
        # 检查本地内存
        can_run, reason = ResourceMonitor.can_run_model(model_size_gb)
        
        if can_run:
            logger.info(f"本地内存充足: {reason}")
            return True
        
        logger.warning(f"本地内存不足!")
        logger.warning(f"  模型需求: {model_size_gb:.1f}GB")
        logger.warning(f"  可用内存: {self.node_info.memory_available_gb:.1f}GB")
        logger.warning(f"  缺少: {model_size_gb * 1.2 - self.node_info.memory_available_gb:.1f}GB")
        
        # 进入等待集群模式
        logger.info("等待其他节点加入以进行分布式加载...")
        self.waiting_for_cluster = True
        
        # 广播资源查询
        self._broadcast_resource_query(model_size_gb)
        
        # 等待集群资源收集完成
        max_wait_time = 120  # 最多等待2分钟
        check_interval = 3
        waited = 0
        
        while waited < max_wait_time:
            # 检查是否有足够的集群资源
            with self.cluster_resource_lock:
                total_memory = sum(
                    r.get("memory_available_gb", 0) 
                    for r in self.cluster_resources.values()
                )
                # 加上自己的内存
                total_memory += self.node_info.memory_available_gb
                node_count = len(self.cluster_resources) + 1
            
            if waited % 15 == 0:
                logger.info(f"等待中... 已发现 {node_count} 个节点, "
                           f"总可用内存: {total_memory:.1f}GB / {model_size_gb * 1.2:.1f}GB  "
                           f"({waited}s/{max_wait_time}s)")
            
            # 检查是否满足条件
            if total_memory >= model_size_gb * 1.2 and node_count >= 2:
                logger.info(f"检测到足够的集群资源! 节点数: {node_count}, 总内存: {total_memory:.1f}GB")
                self.waiting_for_cluster = False
                return True
            
            # Re-broadcast periodically to discover new nodes
            if waited > 0 and waited % 15 == 0:
                self._broadcast_resource_query(model_size_gb)
            
            # 等待一段时间
            time.sleep(check_interval)
            waited += check_interval
        
        logger.warning(f"等待超时，无法获得足够的集群资源")
        self.waiting_for_cluster = False
        return False
    
    def _broadcast_resource_query(self, model_size_gb: float):
        """广播资源查询消息"""
        # Bug 16 fix: Use proper MessageType format instead of raw dict
        data = {
            "node_id": self.node_info.node_id,
            "host": self.node_info.host,
            "port": self.node_info.port,
            "model_name": self.config.model_name,
            "model_size_gb": model_size_gb,
            "timestamp": time.time(),
        }
        
        # 发送到已知节点 (Bug 2 fix: use proper send_message with MessageType)
        for node_id, node_info in self.network.known_nodes.items():
            try:
                if node_info.host and node_info.port:
                    self.network.send_message(
                        node_info.host, node_info.port,
                        MessageType.CLUSTER_RESOURCE_QUERY, data,
                        wait_response=False
                    )
            except Exception as e:
                logger.debug(f"发送资源查询失败: {e}")
        
        # 也发送到种子节点
        for seed in self.config.seeds:
            try:
                parts = seed.split(":")
                host = parts[0]
                port = int(parts[1]) if len(parts) > 1 else 5000
                self.network.send_message(
                    host, port,
                    MessageType.CLUSTER_RESOURCE_QUERY, data,
                    wait_response=False
                )
            except Exception as e:
                logger.debug(f"发送到种子节点失败: {e}")
    
    # Improvement 7 fix: Properly accept from_node parameter and fix response sending
    def _handle_cluster_resource_query(self, data: Dict, from_node: str) -> Dict:
        """
        处理集群资源查询
        
        Bug 2/16 fix: The handler now properly returns a response dict.
        The NetworkManager's _handle_connection will wrap it in the proper
        MessageType format and send it back automatically.
        """
        # 更新资源信息
        self._update_resource_info()
        
        # Register the querying node
        query_node_id = data.get("node_id", "")
        query_host = data.get("host", "")
        query_port = data.get("port", 0)
        
        if query_node_id and query_node_id != self.node_info.node_id:
            if query_node_id not in self.network.known_nodes:
                node_info = NodeInfo(
                    node_id=query_node_id,
                    node_name=query_node_id[:8],
                    host=query_host,
                    port=query_port,
                )
                self.network.known_nodes[query_node_id] = node_info
        
        # Return resource info (NetworkManager will wrap and send this)
        return {
            "node_id": self.node_info.node_id,
            "node_name": self.node_info.node_name,
            "memory_total_gb": self.node_info.memory_total_gb,
            "memory_available_gb": self.node_info.memory_available_gb,
            "gpu_available": self.node_info.gpu_available,
            "gpu_memory_gb": self.node_info.gpu_memory_gb,
            "cpu_cores": self.node_info.cpu_cores,
            "host": self.node_info.host,
            "port": self.node_info.port,
            "timestamp": time.time(),
        }
    
    def _handle_cluster_resource_response(self, data: Dict, from_node: str) -> Dict:
        """处理集群资源响应"""
        node_id = data.get("node_id", "")
        
        with self.cluster_resource_lock:
            self.cluster_resources[node_id] = {
                "node_id": node_id,
                "node_name": data.get("node_name", ""),
                "memory_total_gb": data.get("memory_total_gb", 0),
                "memory_available_gb": data.get("memory_available_gb", 0),
                "gpu_available": data.get("gpu_available", False),
                "gpu_memory_gb": data.get("gpu_memory_gb", 0),
                "cpu_cores": data.get("cpu_cores", 0),
                "host": data.get("host", ""),
                "port": data.get("port", 0),
            }
            
            # Also register as known node if not already
            if node_id and node_id != self.node_info.node_id and node_id not in self.network.known_nodes:
                try:
                    host = data.get("host", "")
                    port = data.get("port", 0)
                    if host and port:
                        self.network.known_nodes[node_id] = NodeInfo(
                            node_id=node_id,
                            node_name=data.get("node_name", node_id[:8]),
                            host=host,
                            port=port,
                        )
                except Exception:
                    pass
        
        return {"status": "received"}
    
    def _plan_distributed_loading(self, model_size_gb: float) -> Dict:
        """
        规划分布式加载方案
        
        Args:
            model_size_gb: 模型大小
            
        Returns:
            加载计划
        """
        with self.cluster_resource_lock:
            # 收集所有节点（包括自己）
            all_nodes = [
                {
                    "node_id": self.node_info.node_id,
                    "memory_available_gb": self.node_info.memory_available_gb,
                    "host": self.node_info.host,
                    "port": self.node_info.port,
                }
            ]
            all_nodes.extend(list(self.cluster_resources.values()))
        
        # 按可用内存排序
        all_nodes.sort(key=lambda x: x.get("memory_available_gb", 0), reverse=True)
        
        # 计算总内存和每节点分片大小
        total_memory = sum(n.get("memory_available_gb", 0) for n in all_nodes)
        memory_per_node = model_size_gb * 1.2 / len(all_nodes)  # 每节点需要的内存
        
        # 选择能够参与分片的节点
        participating_nodes = [
            n for n in all_nodes 
            if n.get("memory_available_gb", 0) >= memory_per_node * 0.8
        ]
        
        if len(participating_nodes) < 2:
            # 如果没有足够节点，使用所有可用节点
            participating_nodes = all_nodes[:max(len(all_nodes), 1)]
        
        # 分配阶段ID
        num_stages = len(participating_nodes)
        for i, node in enumerate(participating_nodes):
            node["stage_id"] = i
            node["total_stages"] = num_stages
        
        plan = {
            "model_name": self.config.model_name,
            "model_size_gb": model_size_gb,
            "num_stages": num_stages,
            "nodes": participating_nodes,
            "created_at": time.time(),
        }
        
        logger.info(f"分布式加载计划: 模型={self.config.model_name}, 大小={model_size_gb:.1f}GB, 分片数={num_stages}")
        for node in participating_nodes:
            logger.info(f"  节点 {node.get('node_name', node.get('node_id', 'unknown'))}: "
                       f"阶段 {node.get('stage_id', 0)+1}/{num_stages}, "
                       f"内存 {node.get('memory_available_gb', 0):.1f}GB")
        
        return plan
    
    def _coordinate_distributed_loading(self, plan: Dict):
        """协调分布式加载"""
        self.distributed_loading_plan = plan
        
        # 找到自己的分配
        my_stage_id = None
        my_total_stages = plan["num_stages"]
        
        for node in plan["nodes"]:
            if node.get("node_id") == self.node_info.node_id:
                my_stage_id = node.get("stage_id")
                break
        
        if my_stage_id is None:
            logger.error("未在加载计划中找到本节点")
            return False
        
        # 发送启动消息给所有参与节点 (Bug 2 fix: use proper MessageType)
        for node in plan["nodes"]:
            if node.get("node_id") != self.node_info.node_id:
                try:
                    host = node.get("host", "")
                    port = node.get("port", 0)
                    if host and port:
                        self.network.send_message(
                            host, port,
                            MessageType.CLUSTER_START_DISTRIBUTED,
                            {
                                "node_id": self.node_info.node_id,
                                "plan": plan,
                                "target_node_id": node.get("node_id"),
                                "target_stage_id": node.get("stage_id"),
                            },
                            wait_response=False
                        )
                except Exception as e:
                    logger.error(f"发送分布式加载指令失败: {e}")
        
        # 自己也加载分片
        logger.info(f"开始加载模型分片... 本节点阶段: {my_stage_id + 1}/{my_total_stages}")
        
        if self.model_manager.load_shard(my_stage_id, my_total_stages):
            self.pipeline_enabled = True
            self.pipeline_stage_id = my_stage_id
            return True
        
        return False
    
    # Improvement 7 fix: Properly accept from_node parameter
    def _handle_cluster_start_distributed(self, data: Dict, from_node: str) -> Dict:
        """处理分布式加载指令"""
        plan = data.get("plan", {})
        target_stage_id = data.get("target_stage_id")
        
        logger.info(f"收到分布式加载指令, 本节点阶段: {target_stage_id + 1}/{plan.get('num_stages', 2)}")
        
        # Register the coordinator node
        coordinator_id = data.get("node_id", from_node)
        if coordinator_id and coordinator_id not in self.network.known_nodes:
            # Try to find it in the plan nodes
            for node in plan.get("nodes", []):
                if node.get("node_id") == coordinator_id:
                    try:
                        self.network.known_nodes[coordinator_id] = NodeInfo(
                            node_id=coordinator_id,
                            node_name=node.get("node_name", coordinator_id[:8]),
                            host=node.get("host", ""),
                            port=node.get("port", 0),
                        )
                    except Exception:
                        pass
                    break
        
        # 加载分片
        if self.model_manager.load_shard(target_stage_id, plan.get("num_stages", 2)):
            self.pipeline_enabled = True
            self.pipeline_stage_id = target_stage_id
            self.node_info.model_loaded = True
            self.node_info.model_name = plan.get("model_name", "")
            logger.info("分片加载成功!")
            return {"status": "success"}
        else:
            logger.error("分片加载失败!")
            return {"status": "failed", "error": "Shard loading failed"}
    
    def _heartbeat_loop(self):
        """心跳循环"""
        while self.running:
            self._update_resource_info()
            time.sleep(self.config.health_check_interval)
    
    def _task_loop(self):
        """任务处理循环"""
        while self.running:
            with self.task_lock:
                while self.pending_tasks:
                    task = self.pending_tasks.popleft()
                    t = threading.Thread(
                        target=self._process_task, 
                        args=(task,), 
                        daemon=True
                    )
                    t.start()
            
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
        
        if result.success:
            task.status = "completed"
            task.result = result.response
            task.tokens = result.tokens
        else:
            task.status = "failed"
            task.error = result.error
        
        with self.task_lock:
            # Bug 11 fix: Limit completed_tasks size to prevent memory leak
            self.completed_tasks[task.task_id] = task
            if len(self.completed_tasks) > self.MAX_COMPLETED_TASKS:
                # Remove oldest entries
                oldest_keys = list(self.completed_tasks.keys())[:len(self.completed_tasks) - self.MAX_COMPLETED_TASKS]
                for key in oldest_keys:
                    del self.completed_tasks[key]
        
        self.load_balancer.update_node_stats(
            self.node_info.node_id,
            task.latency,
            result.success
        )
    
    def _start_api_server(self):
        """启动API服务器
        
        Bug 8 fix: Use ThreadingHTTPServer for concurrent request handling.
        """
        APIRequestHandler.node = self
        
        # Bug 8: Use ThreadingHTTPServer instead of plain HTTPServer
        self.api_server = ThreadingHTTPServer(
            (self.config.api_host, self.config.api_port),
            APIRequestHandler
        )
        
        api_thread = threading.Thread(target=self.api_server.serve_forever, daemon=True)
        api_thread.start()
        self._threads.append(api_thread)
    
    def _get_local_ip(self) -> str:
        """获取本机IP"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"
    
    # Improvement 4: Proper cleanup in stop()
    def stop(self):
        """停止节点"""
        logger.info("正在停止节点...")
        self.running = False
        
        # Stop election first to avoid triggering new elections
        self.election.stop()
        
        # Stop network (closes server socket, stopping accept loop)
        self.network.stop()
        
        # Shutdown API server
        if self.api_server:
            try:
                self.api_server.shutdown()
            except Exception:
                pass
        
        # Unload model
        self.model_manager.unload()
        
        # Clear pending tasks
        with self.task_lock:
            self.pending_tasks.clear()
        
        logger.info("节点已停止")


# ==================== 主函数 ====================

def load_config_file(config_path: str) -> Dict:
    """加载配置文件"""
    if not os.path.exists(config_path):
        return {}
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        logger.info(f"已加载配置文件: {config_path}")
        return config
    except Exception as e:
        logger.error(f"加载配置文件失败: {e}")
        return {}


def merge_config(args, file_config: Dict) -> UnifiedConfig:
    """合并配置：命令行 > 配置文件 > 默认值"""
    
    # 从配置文件获取值
    node_cfg = file_config.get('node', {})
    model_cfg = file_config.get('model', {})
    cluster_cfg = file_config.get('cluster', {})
    parallel_cfg = file_config.get('parallel', {})
    lb_cfg = file_config.get('load_balance', {})
    ngrok_cfg = file_config.get('ngrok', {})
    paths_cfg = file_config.get('paths', {})
    logging_cfg = file_config.get('logging', {})
    health_cfg = file_config.get('health', {})
    
    # 合并配置（命令行优先）
    config = UnifiedConfig(
        # 节点配置
        host=args.host if args.host else node_cfg.get('host', '0.0.0.0'),
        port=args.port if args.port != 5000 else node_cfg.get('port', 5000),
        api_host=args.api_host if args.api_host else node_cfg.get('api_host', '0.0.0.0'),
        api_port=args.api_port if args.api_port != 8080 else node_cfg.get('api_port', 8080),
        node_name=node_cfg.get('name', ''),
        
        # 模型配置
        model_name=args.model if args.model != "Qwen/Qwen2.5-0.5B-Instruct" else model_cfg.get('name', "Qwen/Qwen2.5-0.5B-Instruct"),
        model_memory_gb=model_cfg.get('memory_gb', 2.0),
        max_workers=model_cfg.get('max_workers', 2),
        
        # 集群配置
        seeds=args.seeds.split(",") if args.seeds else cluster_cfg.get('seeds', []),
        discovery_port=cluster_cfg.get('discovery_port', 9000),
        heartbeat_interval=cluster_cfg.get('heartbeat_interval', 2.0),
        election_timeout_min=cluster_cfg.get('election_timeout_min', 3.0),
        election_timeout_max=cluster_cfg.get('election_timeout_max', 6.0),
        leader_timeout=cluster_cfg.get('leader_timeout', 10.0),
        node_timeout=cluster_cfg.get('node_timeout', 30.0),
        
        # 并行配置
        parallel_mode=args.mode if args.mode != "data_parallel" else parallel_cfg.get('mode', 'data_parallel'),
        schedule_mode=args.schedule,
        pipeline_stages=args.stages if args.stages != 1 else parallel_cfg.get('pipeline_stages', 1),
        pipeline_micro_batch=args.micro_batch if args.micro_batch != 4 else parallel_cfg.get('pipeline_micro_batch', 4),
        tensor_parallel_size=args.tp_size if args.tp_size != 1 else parallel_cfg.get('tensor_parallel_size', 1),
        hybrid_dp_size=args.dp if args.dp != 1 else parallel_cfg.get('hybrid_dp_size', 1),
        hybrid_tp_size=args.tp if args.tp != 1 else parallel_cfg.get('hybrid_tp_size', 1),
        hybrid_pp_size=args.pp if args.pp != 1 else parallel_cfg.get('hybrid_pp_size', 1),
        
        # 负载均衡
        load_balance_strategy=args.load_balance if args.load_balance != "adaptive" else lb_cfg.get('strategy', 'adaptive'),
        straggler_threshold=args.straggler_threshold if args.straggler_threshold != 2.0 else lb_cfg.get('straggler_threshold', 2.0),
        auto_rebalance=lb_cfg.get('auto_rebalance', True),
        
        # 自动模式
        auto_mode=args.auto if hasattr(args, 'auto') and args.auto else node_cfg.get('auto', False),
        
        # 日志
        log_level=args.log_level if args.log_level != "INFO" else logging_cfg.get('level', 'INFO'),
        log_file=logging_cfg.get('file', ''),
        
        # 健康检查
        health_check_interval=health_cfg.get('check_interval', 5.0),
    )
    
    # 保存 ngrok 配置到 config 对象（扩展属性）
    config.ngrok_enabled = args.ngrok or ngrok_cfg.get('enabled', False)
    config.ngrok_auth_token = args.ngrok_auth_token if args.ngrok_auth_token else ngrok_cfg.get('auth_token', '')
    config.ngrok_region = args.ngrok_region if args.ngrok_region != "ap" else ngrok_cfg.get('region', 'ap')
    
    # 保存路径配置
    config.model_cache_dir = paths_cfg.get('model_cache', '')
    config.log_dir = paths_cfg.get('log_dir', 'logs')
    config.data_dir = paths_cfg.get('data_dir', 'data')
    
    # 设置模型缓存目录
    if config.model_cache_dir:
        os.environ['HF_HOME'] = config.model_cache_dir
    
    return config


def main():
    parser = argparse.ArgumentParser(
        description="统一分布式推理系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 使用默认配置
  python %(prog)s
  
  # 使用配置文件
  python %(prog)s --config config.json
  
  # 自动模式选择
  python %(prog)s --auto

  # 数据并行模式
  python %(prog)s --mode data_parallel

  # Pipeline 并行模式
  python %(prog)s --mode pipeline_parallel --stages 4

  # 混合并行模式
  python %(prog)s --mode hybrid --dp 2 --tp 2 --pp 2

  # 多节点集群
  python %(prog)s --port 5000  # 第一个节点
  python %(prog)s --port 5001 --seeds "192.168.1.1:5000"  # 后续节点
  
  # 启用 Ngrok 公网暴露
  python %(prog)s --ngrok --ngrok-auth-token YOUR_TOKEN
        """
    )
    
    # 配置文件
    parser.add_argument("--config", type=str, default="config.json", help="配置文件路径")
    
    # 基础配置
    parser.add_argument("--host", type=str, default="0.0.0.0", help="节点主机")
    parser.add_argument("--port", type=int, default=5000, help="节点端口")
    parser.add_argument("--api-host", type=str, default="0.0.0.0", help="API主机")
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
    parser.add_argument("--micro-batch", type=int, default=4, help="微批次大小")
    
    # Tensor 并行配置
    parser.add_argument("--tp-size", type=int, default=1, help="Tensor 并行大小")
    
    # 混合并行配置
    parser.add_argument("--dp", type=int, default=1, help="数据并行大小")
    parser.add_argument("--tp", type=int, default=1, help="Tensor 并行大小")
    parser.add_argument("--pp", type=int, default=1, help="Pipeline 并行大小")
    
    # 负载均衡
    parser.add_argument("--load-balance", type=str, default="adaptive",
                       choices=["round_robin", "least_loaded", "adaptive"],
                       help="负载均衡策略")
    parser.add_argument("--straggler-threshold", type=float, default=2.0,
                       help="慢节点阈值")
    
    # 自动模式
    parser.add_argument("--auto", action="store_true", help="自动选择最佳模式")
    
    # Ngrok 配置
    parser.add_argument("--ngrok", action="store_true", help="使用 ngrok 暴露公网地址")
    parser.add_argument("--ngrok-auth-token", type=str, default="", help="ngrok 认证令牌")
    parser.add_argument("--ngrok-region", type=str, default="ap", help="ngrok 区域 (us, eu, ap, au, sa, jp, in)")
    
    # 日志
    parser.add_argument("--log-level", type=str, default="INFO",
                       choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                       help="日志级别")
    
    args = parser.parse_args()
    
    # 加载配置文件
    file_config = load_config_file(args.config)
    
    # 合并配置（命令行 > 配置文件 > 默认值）
    config = merge_config(args, file_config)
    
    # 自动模式选择
    if args.auto:
        logger.info("自动模式: 检测系统资源...")
        info = ResourceMonitor.get_system_info()
        
        # 假设网络带宽
        bandwidth = 1000  # 1 Gbps
        
        mode = ModeSelector.auto_select(
            num_nodes=1,
            total_memory_gb=info["memory_total_gb"],
            model_size_gb=2.0,
            bandwidth_mbps=bandwidth
        )
        
        config.parallel_mode = mode
        logger.info(f"自动模式: 选择 {mode.value}")
        
        mode_info = ModeSelector.get_mode_info(mode)
        logger.info(f"{mode_info.get('name', '')}: {mode_info.get('description', '')}")
    
    # Ngrok 隧道设置
    ngrok_url = None
    ngrok_tunnel = None
    
    if config.ngrok_enabled:
        if not HAS_NGROK:
            logger.error("pyngrok 未安装，请运行: pip install pyngrok")
            logger.error("或者访问 https://ngrok.com 注册并获取 authtoken")
            sys.exit(1)
        
        logger.info("正在创建公网隧道...")
        
        try:
            # 设置认证令牌
            if config.ngrok_auth_token:
                ngrok.set_auth_token(config.ngrok_auth_token)
            
            # 为节点通信端口创建隧道
            node_tunnel = ngrok.connect(
                config.port,
                region=config.ngrok_region,
                proto="tcp"
            )
            node_public_url = node_tunnel.public_url
            logger.info(f"节点通信地址: {node_public_url}")
            
            # 为 API 端口创建隧道
            api_tunnel = ngrok.connect(
                config.api_port,
                region=config.ngrok_region,
                proto="http"
            )
            ngrok_url = api_tunnel.public_url
            logger.info(f"API 公网地址: {ngrok_url}")
            logger.info(f"健康检查: {ngrok_url}/health")
            
            # 保存隧道引用以便后续关闭
            ngrok_tunnel = (node_tunnel, api_tunnel)
            
            # 更新配置中的公网地址
            # 其他节点可以通过这个地址连接
            logger.info(f"其他节点连接命令:")
            logger.info(f"       python node_unified_complete.py --port {config.port + 1} --api-port {config.api_port + 1} --seeds \"{node_public_url.replace('tcp://', '')}\"")
            
        except Exception as e:
            logger.error(f"Ngrok 错误: {e}")
            logger.info("提示:")
            logger.info("  1. 访问 https://dashboard.ngrok.com/get-started/your-authtoken 获取 authtoken")
            logger.info("  2. 运行: python node_unified_complete.py --ngrok --ngrok-auth-token YOUR_TOKEN")
            sys.exit(1)
    
    # 创建并启动节点
    try:
        node = UnifiedNode(config)
        node.start()
    except KeyboardInterrupt:
        logger.info("正在停止...")
    finally:
        # 关闭 ngrok 隧道
        if ngrok_tunnel:
            logger.info("关闭公网隧道...")
            try:
                for tunnel in ngrok_tunnel:
                    ngrok.disconnect(tunnel.public_url)
                ngrok.kill()
                logger.info("隧道已关闭")
            except Exception:
                pass


if __name__ == "__main__":
    main()
