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
                print(f"[负载均衡] ⚠️ 发现慢节点: {node_id[:8]} (延迟: {stats['avg_latency']:.3f}s)")
        elif node_id in self.straggler_nodes:
            self.straggler_nodes.discard(node_id)
            print(f"[负载均衡] [OK] 节点恢复: {node_id[:8]}")
    
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

class DistributedInferenceCoordinator:
    """分布式推理协调器 - 管理 Pipeline 并行推理"""
    
    def __init__(self, node: 'UnifiedNode'):
        self.node = node
        self.pipeline_groups: Dict[str, List[str]] = {}  # pipeline_id -> [node_id, ...]
        self.stage_assignments: Dict[str, int] = {}  # node_id -> stage_id
        self.pending_stages: Dict[str, Dict[int, Any]] = {}  # task_id -> {stage_id: hidden_states}
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
            
            print(f"[Pipeline] 创建 Pipeline 组 {pipeline_id[:8]}: {len(nodes)} 个节点, {total_stages} 个阶段")
    
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
            
            # 初始化任务状态
            with self.lock:
                self.pending_stages[task_id] = {
                    "prompt": prompt,
                    "max_tokens": max_tokens,
                    "current_stage": 0,
                    "start_time": start_time,
                    "hidden_states": None,
                }
            
            # 发送到第一阶段节点
            if first_node_id == self.node.node_info.node_id:
                # 本地执行第一阶段
                return self._execute_first_stage(task_id, prompt)
            else:
                # 远程执行第一阶段
                return self._send_to_node(first_node_id, {
                    "type": "pipeline_stage",
                    "task_id": task_id,
                    "stage": 0,
                    "prompt": prompt,
                    "max_tokens": max_tokens,
                })
            
        except Exception as e:
            print(f"[Pipeline] 启动推理失败: {e}")
            traceback.print_exc()
            return {"success": False, "error": str(e)}
    
    def _execute_first_stage(self, task_id: str, prompt: str) -> Dict:
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
                
                # 获取下一节点
                nodes = self.pipeline_groups.get("default", [])
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
                    result = self.node.model_manager.inference(
                        prompt, 
                        max_tokens=self.pending_stages[task_id]["max_tokens"]
                    )
                    
                    # 清理
                    with self.lock:
                        del self.pending_stages[task_id]
                    
                    return {
                        "success": True,
                        "response": result.response,
                        "tokens": result.tokens,
                        "latency": time.time() - self.pending_stages.get(task_id, {}).get("start_time", time.time()),
                    }
                    
        except Exception as e:
            print(f"[Pipeline] 第一阶段执行失败: {e}")
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
            
            # 获取下一阶段
            nodes = self.pipeline_groups.get("default", [])
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
            print(f"[Pipeline] 处理阶段结果失败: {e}")
            traceback.print_exc()
            return {"success": False, "error": str(e)}
    
    def _generate_final_output(self, task_id: str, hidden_states: torch.Tensor) -> Dict:
        """生成最终输出"""
        try:
            # 通过 lm_head
            with torch.no_grad():
                if hasattr(self.node.model_manager.model, 'lm_head'):
                    logits = self.node.model_manager.model.lm_head(hidden_states)
                    next_token = torch.argmax(logits[:, -1, :], dim=-1)
                    
                    # 解码
                    response = self.node.model_manager.tokenizer.decode(
                        next_token, 
                        skip_special_tokens=True
                    )
                else:
                    response = ""
            
            # 获取延迟
            with self.lock:
                task_info = self.pending_stages.get(task_id, {})
                latency = time.time() - task_info.get("start_time", time.time())
                
                # 清理
                if task_id in self.pending_stages:
                    del self.pending_stages[task_id]
                
                # 更新统计
                self.total_pipeline_inferences += 1
                self.total_pipeline_latency += latency
            
            return {
                "success": True,
                "response": response,
                "tokens": 1,  # Pipeline 单步生成
                "latency": latency,
            }
            
        except Exception as e:
            print(f"[Pipeline] 生成输出失败: {e}")
            traceback.print_exc()
            return {"success": False, "error": str(e)}
    
    def _send_to_node(self, node_id: str, message: Dict) -> Dict:
        """发送消息到节点"""
        try:
            # 使用网络管理器发送
            return self.node.network.send_message(node_id, message)
        except Exception as e:
            print(f"[Pipeline] 发送消息失败: {e}")
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
                self.messages_received += 1
                self.bytes_received += len(data)
                
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
                            encoded = self._encode_message(response_msg)
                            conn.sendall(encoded)
                            self.bytes_sent += len(encoded)
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
                
                if response_data:
                    self.bytes_received += len(response_data)
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
        
        self.elections_started += 1
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
                print(f"[选举] 投票给 {candidate_id[:8]}")
        
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
        print(f"[选举] 🎉 成为领导节点! 任期 {self.current_term}")
        
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
            
            print(f"[模型] [OK] 加载完成!")
            print(f"   参数量: {param_count/1e9:.2f}B")
            print(f"   大小: {self.model_size_gb:.2f}GB")
            print(f"   设备: {self.device}")
            print(f"   时间: {self.load_time:.1f}s")
            
            return True
            
        except Exception as e:
            print(f"[模型] [ERROR] 加载失败: {e}")
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
        
        import gc
        gc.collect()
        
        print("[模型] 已卸载")
    
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
        except:
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
            print("[模型] PyTorch未安装，无法加载模型分片")
            return False
        
        start_time = time.time()
        
        try:
            print(f"[模型] 加载模型分片: 阶段 {stage_id+1}/{total_stages}")
            
            # 加载完整模型配置
            config = AutoConfig.from_pretrained(
                self.config.model_name,
                trust_remote_code=True
            )
            
            # 获取总层数
            total_layers = self.get_layer_count()
            if total_layers == 0:
                print("[模型] 无法获取模型层数，回退到完整模型加载")
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
            
            print(f"   层范围: {layer_start}-{layer_end-1} (共 {layer_end - layer_start} 层)")
            
            # 加载 tokenizer
            print("   [1/2] 加载Tokenizer...")
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.config.model_name,
                trust_remote_code=True
            )
            
            if self.tokenizer.pad_token is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token
            
            # 加载完整模型（暂时，实际应用中应该只加载分片）
            # 注意：真正的分片加载需要更复杂的实现，这里先加载完整模型
            # 然后只使用指定层
            print("   [2/2] 加载模型分片...")
            
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
            
            print(f"[模型] [OK] 分片加载完成!")
            print(f"   阶段: {stage_id+1}/{total_stages}")
            print(f"   层: {layer_start}-{layer_end-1}")
            print(f"   类型: {'第一阶段' if is_first else '最后阶段' if is_last else '中间阶段'}")
            print(f"   设备: {self.device}")
            print(f"   时间: {self.load_time:.1f}s")
            
            return True
            
        except Exception as e:
            print(f"[模型] [ERROR] 分片加载失败: {e}")
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
            print(f"[Pipeline] 前向传播错误: {e}")
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
            
            messages = body.get("messages", [])
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
            
            prompt = body.get("prompt", "")
            model = body.get("model", self.node.config.model_name)
            max_tokens = body.get("max_tokens", 256)
            temperature = body.get("temperature", 0.7)
            
            result = self.node.model_manager.inference(
                prompt,
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
            
            prompt = body.get("prompt", "")
            max_tokens = body.get("max_tokens", 256)
            temperature = body.get("temperature", 0.7)
            
            result = self.node.model_manager.inference(
                prompt,
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
    
    def __init__(self, config: UnifiedConfig):
        self.config = config
        
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
        self.completed_tasks: Dict[str, TaskInfo] = {}
        self.task_lock = threading.Lock()
        
        # Pipeline
        self.pipeline_stages: List[PipelineStage] = []
        self.pipeline_enabled = False
        self.pipeline_stage_id = -1
        
        # 状态
        self.running = False
        self.api_server: Optional[HTTPServer] = None
        self.start_time = time.time()
    
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
        
        # 加载模型
        if self.config.parallel_mode == ParallelMode.PIPELINE_PARALLEL:
            # Pipeline 并行模式 - 加载模型分片
            total_stages = self.config.pipeline_stages
            if total_stages <= 1:
                print("[警告] Pipeline 阶段数无效，使用默认值 2")
                total_stages = 2
            
            # 确定当前节点的阶段ID
            # 领导节点为阶段 0，其他节点按加入顺序分配
            if self.election.state == NodeRole.LEADER:
                stage_id = 0
            else:
                # 工作节点根据配置或自动分配阶段
                stage_id = len(self.network.peers) % total_stages
            
            print(f"\n[Pipeline] 加载模型分片...")
            print(f"[Pipeline] 阶段: {stage_id + 1}/{total_stages}")
            
            if not self.model_manager.load_shard(stage_id, total_stages):
                print("[错误] 模型分片加载失败")
                return
            
            self.pipeline_enabled = True
            self.pipeline_stage_id = stage_id
            
        elif self.config.parallel_mode == ParallelMode.HYBRID:
            # 混合并行模式
            # TODO: 实现混合并行
            print("[警告] 混合并行模式尚未完全实现，使用数据并行")
            if not self.model_manager.load():
                print("[错误] 模型加载失败")
                return
        else:
            # 数据并行模式 - 加载完整模型
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
        
        print("\n" + "=" * 60)
        print("[系统] [OK] 节点启动完成!")
        print(f"[API] http://{self.config.api_host}:{self.config.api_port}")
        print("=" * 60)
        print("\n按 Ctrl+C 停止...\n")
        
        # 主循环
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n[系统] 正在停止...")
            self.stop()
    
    def _print_banner(self):
        """打印启动横幅"""
        print("\n" + "=" * 60)
        print(f"  统一分布式推理系统 v{VERSION}")
        print("=" * 60)
        print(f"  节点ID:   {self.config.node_id[:8]}")
        print(f"  节点名称: {self.config.node_name}")
        print(f"  并行模式: {self.config.parallel_mode.value}")
        print(f"  调度模式: {self.config.schedule_mode.value}")
        print(f"  模型:     {self.config.model_name}")
        print("=" * 60)
        
        # 显示模式信息
        mode_info = ModeSelector.get_mode_info(self.config.parallel_mode)
        if mode_info:
            print(f"\n【{mode_info.get('name', '')}】")
            print(f"  {mode_info.get('description', '')}")
            print(f"  优点: {', '.join(mode_info.get('pros', []))}")
            print(f"  缺点: {', '.join(mode_info.get('cons', []))}")
    
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
    
    def _handle_pipeline_data(self, data: Dict, from_node: str) -> Dict:
        """处理 Pipeline 数据"""
        # TODO: 实现 Pipeline 数据处理
        return {"status": "received"}
    
    def _on_become_leader(self):
        """成为领导节点回调"""
        print("[领导] 👑 成为领导节点，开始接受请求")
    
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
        
        if result.success:
            task.status = "completed"
            task.result = result.response
            task.tokens = result.tokens
        else:
            task.status = "failed"
            task.error = result.error
        
        with self.task_lock:
            self.completed_tasks[task.task_id] = task
        
        self.load_balancer.update_node_stats(
            self.node_info.node_id,
            task.latency,
            result.success
        )
    
    def _start_api_server(self):
        """启动API服务器"""
        APIRequestHandler.node = self
        
        self.api_server = HTTPServer(
            (self.config.api_host, self.config.api_port),
            APIRequestHandler
        )
        
        threading.Thread(target=self.api_server.serve_forever, daemon=True).start()
    
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

def load_config_file(config_path: str) -> Dict:
    """加载配置文件"""
    if not os.path.exists(config_path):
        return {}
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        print(f"[配置] 已加载配置文件: {config_path}")
        return config
    except Exception as e:
        print(f"[配置] 加载配置文件失败: {e}")
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
        auto_mode=args.auto,
        
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
        print("\n[自动模式] 检测系统资源...")
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
        print(f"[自动模式] 选择模式: {mode.value}")
        
        mode_info = ModeSelector.get_mode_info(mode)
        print(f"[自动模式] {mode_info.get('name', '')}: {mode_info.get('description', '')}")
    
    # Ngrok 隧道设置
    ngrok_url = None
    ngrok_tunnel = None
    
    if config.ngrok_enabled:
        if not HAS_NGROK:
            print("\n[错误] pyngrok 未安装，请运行: pip install pyngrok")
            print("       或者访问 https://ngrok.com 注册并获取 authtoken")
            sys.exit(1)
        
        print("\n[Ngrok] 正在创建公网隧道...")
        
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
            print(f"[Ngrok] 节点通信地址: {node_public_url}")
            
            # 为 API 端口创建隧道
            api_tunnel = ngrok.connect(
                config.api_port,
                region=config.ngrok_region,
                proto="http"
            )
            ngrok_url = api_tunnel.public_url
            print(f"[Ngrok] API 公网地址: {ngrok_url}")
            print(f"[Ngrok] 健康检查: {ngrok_url}/health")
            print(f"[Ngrok] Web UI: {ngrok_url}")
            
            # 保存隧道引用以便后续关闭
            ngrok_tunnel = (node_tunnel, api_tunnel)
            
            # 更新配置中的公网地址
            # 其他节点可以通过这个地址连接
            print(f"\n[Ngrok] 其他节点连接命令:")
            print(f"       python node_unified_complete.py --port {config.port + 1} --api-port {config.api_port + 1} --seeds \"{node_public_url.replace('tcp://', '')}\"")
            
        except Exception as e:
            print(f"[Ngrok 错误] {e}")
            print("\n提示:")
            print("  1. 访问 https://dashboard.ngrok.com/get-started/your-authtoken 获取 authtoken")
            print("  2. 运行: python node_unified_complete.py --ngrok --ngrok-auth-token YOUR_TOKEN")
            sys.exit(1)
    
    # 创建并启动节点
    try:
        node = UnifiedNode(config)
        node.start()
    except KeyboardInterrupt:
        print("\n[系统] 正在停止...")
    finally:
        # 关闭 ngrok 隧道
        if ngrok_tunnel:
            print("\n[Ngrok] 关闭公网隧道...")
            try:
                for tunnel in ngrok_tunnel:
                    ngrok.disconnect(tunnel.public_url)
                ngrok.kill()
                print("[Ngrok] 隧道已关闭")
            except:
                pass


if __name__ == "__main__":
    main()
