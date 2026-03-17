#!/usr/bin/env python3
"""
分布式大模型推理系统 - 联合分布式推理模块
==========================================

核心功能:
1. 模型分片管理 - 自动将大模型分割到多个节点
2. Pipeline并行协调 - 协调多节点流水线推理
3. 负载均衡 - 智能分配推理任务
4. 故障恢复 - 节点故障时自动重新分片

工作原理:
1. 领导节点分析模型结构和集群资源
2. 根据资源情况决定分片策略
3. 将模型分片分配到各节点
4. 协调Pipeline推理流程
"""

import os
import sys
import time
import json
import uuid
import threading
import pickle
import zlib
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
from enum import Enum
import socket

try:
    import torch
    import torch.nn as nn
    from transformers import AutoModelForCausalLM, AutoTokenizer, AutoConfig
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False
    print("警告: torch/transformers未安装")


# ==================== 枚举定义 ====================

class ShardingStrategy(Enum):
    """分片策略"""
    DATA_PARALLEL = "data_parallel"       # 数据并行：每节点完整模型
    PIPELINE_PARALLEL = "pipeline_parallel"  # Pipeline并行：按层分片
    TENSOR_PARALLEL = "tensor_parallel"   # Tensor并行：按注意力头分片
    HYBRID = "hybrid"                     # 混合并行


class ShardState(Enum):
    """分片状态"""
    INITIALIZING = "initializing"
    LOADING = "loading"
    READY = "ready"
    RUNNING = "running"
    ERROR = "error"
    UNLOADED = "unloaded"


# ==================== 数据结构 ====================

@dataclass
class ModelShard:
    """模型分片信息"""
    shard_id: int
    layer_start: int
    layer_end: int
    size_gb: float
    node_id: Optional[str] = None
    state: ShardState = ShardState.INITIALIZING
    
    # 特殊标记
    has_embedding: bool = False
    has_output: bool = False
    
    def to_dict(self) -> Dict:
        return {
            "shard_id": self.shard_id,
            "layer_start": self.layer_start,
            "layer_end": self.layer_end,
            "size_gb": self.size_gb,
            "node_id": self.node_id,
            "state": self.state.value,
            "has_embedding": self.has_embedding,
            "has_output": self.has_output,
        }


@dataclass
class PipelineStage:
    """Pipeline阶段"""
    stage_id: int
    shard: ModelShard
    input_buffer: List = field(default_factory=list)
    output_buffer: List = field(default_factory=list)
    processing: bool = False


# ==================== 模型分析器 ====================

class ModelAnalyzer:
    """模型分析器"""
    
    @staticmethod
    def analyze_model(model_name: str) -> Dict:
        """分析模型结构"""
        if not HAS_TORCH:
            return {"error": "PyTorch未安装"}
        
        try:
            config = AutoConfig.from_pretrained(model_name)
            
            info = {
                "model_name": model_name,
                "hidden_size": getattr(config, 'hidden_size', 0),
                "num_layers": getattr(config, 'num_hidden_layers', 0),
                "num_attention_heads": getattr(config, 'num_attention_heads', 0),
                "vocab_size": getattr(config, 'vocab_size', 0),
                "intermediate_size": getattr(config, 'intermediate_size', 0),
            }
            
            # 估算参数量和内存
            if info['hidden_size'] > 0 and info['num_layers'] > 0:
                embed_params = info['vocab_size'] * info['hidden_size']
                attention_params = 4 * info['hidden_size'] * info['hidden_size'] * info['num_layers']
                mlp_params = 2 * info['hidden_size'] * info['intermediate_size'] * info['num_layers']
                output_params = info['vocab_size'] * info['hidden_size']
                
                total_params = embed_params + attention_params + mlp_params + output_params
                info['estimated_params'] = total_params
                info['estimated_size_fp32'] = total_params * 4 / (1024**3)
                info['estimated_size_fp16'] = total_params * 2 / (1024**3)
                
                # 每层大小
                layer_params = attention_params / info['num_layers'] + mlp_params / info['num_layers']
                info['layer_size_fp16'] = layer_params * 2 / (1024**3)
            
            return info
            
        except Exception as e:
            return {"error": str(e)}
    
    @staticmethod
    def calculate_shards(model_info: Dict, num_shards: int) -> List[ModelShard]:
        """计算分片方案"""
        if "error" in model_info:
            return []
        
        num_layers = model_info.get("num_layers", 0)
        if num_layers == 0:
            return []
        
        layer_size = model_info.get("layer_size_fp16", 0.1)
        embed_size = model_info.get("vocab_size", 0) * model_info.get("hidden_size", 0) * 2 / (1024**3)
        
        # 计算每分片层数
        layers_per_shard = num_layers // num_shards
        extra_layers = num_layers % num_shards
        
        shards = []
        current_layer = 0
        
        for i in range(num_shards):
            # 分配层数
            num_layers_this = layers_per_shard
            if i < extra_layers:
                num_layers_this += 1
            
            layer_start = current_layer
            layer_end = current_layer + num_layers_this - 1
            
            # 计算大小
            size = num_layers_this * layer_size
            
            # 第一个分片包含embedding
            has_embedding = (i == 0)
            if has_embedding:
                size += embed_size
            
            # 最后一个分片包含output
            has_output = (i == num_shards - 1)
            
            shards.append(ModelShard(
                shard_id=i,
                layer_start=layer_start,
                layer_end=layer_end,
                size_gb=size,
                has_embedding=has_embedding,
                has_output=has_output,
            ))
            
            current_layer = layer_end + 1
        
        return shards


# ==================== 分片管理器 ====================

class ShardingManager:
    """分片管理器"""
    
    def __init__(self, model_name: str):
        self.model_name = model_name
        self.model_info = ModelAnalyzer.analyze_model(model_name)
        self.shards: List[ModelShard] = []
        self.strategy = ShardingStrategy.DATA_PARALLEL
        
        # 节点到分片的映射
        self.node_shard_map: Dict[str, int] = {}
        self.shard_node_map: Dict[int, str] = {}
    
    def plan_sharding(self, nodes_info: Dict[str, Dict], strategy: ShardingStrategy = None) -> List[ModelShard]:
        """规划分片方案"""
        if "error" in self.model_info:
            print(f"[分片] 模型分析失败: {self.model_info['error']}")
            return []
        
        model_size = self.model_info.get("estimated_size_fp16", 2.0)
        
        # 计算集群总资源
        total_memory = sum(n.get("memory_available_gb", 0) for n in nodes_info.values())
        num_nodes = len(nodes_info)
        
        # 决定策略
        if strategy:
            self.strategy = strategy
        else:
            # 自动选择策略
            avg_memory = total_memory / num_nodes if num_nodes > 0 else 0
            
            if avg_memory >= model_size * 1.5:
                # 每个节点都能装下完整模型
                self.strategy = ShardingStrategy.DATA_PARALLEL
            elif total_memory >= model_size * 1.5:
                # 需要分片
                self.strategy = ShardingStrategy.PIPELINE_PARALLEL
            else:
                # 资源不足
                print(f"[分片] 警告: 集群资源可能不足")
                self.strategy = ShardingStrategy.PIPELINE_PARALLEL
        
        print(f"[分片] 选择策略: {self.strategy.value}")
        
        # 创建分片
        if self.strategy == ShardingStrategy.DATA_PARALLEL:
            # 数据并行：每个节点完整模型
            self.shards = [
                ModelShard(
                    shard_id=i,
                    layer_start=0,
                    layer_end=self.model_info.get("num_layers", 0) - 1,
                    size_gb=model_size,
                    has_embedding=True,
                    has_output=True,
                )
                for i in range(num_nodes)
            ]
        
        elif self.strategy == ShardingStrategy.PIPELINE_PARALLEL:
            # Pipeline并行：按层分片
            self.shards = ModelAnalyzer.calculate_shards(self.model_info, num_nodes)
        
        return self.shards
    
    def assign_shards(self, nodes_info: Dict[str, Dict]) -> Dict[str, int]:
        """分配分片到节点"""
        assignments = {}
        
        # 按资源排序节点
        sorted_nodes = sorted(
            nodes_info.items(),
            key=lambda x: x[1].get("memory_available_gb", 0),
            reverse=True
        )
        
        for i, (node_id, node_info) in enumerate(sorted_nodes):
            if i < len(self.shards):
                shard = self.shards[i]
                shard.node_id = node_id
                shard.state = ShardState.INITIALIZING
                
                assignments[node_id] = shard.shard_id
                self.node_shard_map[node_id] = shard.shard_id
                self.shard_node_map[shard.shard_id] = node_id
        
        return assignments
    
    def get_shard_for_node(self, node_id: str) -> Optional[ModelShard]:
        """获取节点的分片"""
        shard_id = self.node_shard_map.get(node_id)
        if shard_id is not None:
            for shard in self.shards:
                if shard.shard_id == shard_id:
                    return shard
        return None
    
    def get_node_for_shard(self, shard_id: int) -> Optional[str]:
        """获取分片的节点"""
        return self.shard_node_map.get(shard_id)
    
    def update_shard_state(self, shard_id: int, state: ShardState):
        """更新分片状态"""
        for shard in self.shards:
            if shard.shard_id == shard_id:
                shard.state = state
                break


# ==================== Pipeline协调器 ====================

class PipelineCoordinator:
    """Pipeline协调器"""
    
    def __init__(self, shards: List[ModelShard]):
        self.shards = shards
        self.num_stages = len(shards)
        
        # Pipeline阶段
        self.stages: Dict[int, PipelineStage] = {}
        for shard in shards:
            self.stages[shard.shard_id] = PipelineStage(
                stage_id=shard.shard_id,
                shard=shard,
            )
        
        # 请求跟踪
        self.active_requests: Dict[str, Dict] = {}
        self.request_results: Dict[str, Any] = {}
        
        # 锁
        self.lock = threading.Lock()
    
    def start_inference(self, request_id: str, input_data: Any) -> bool:
        """开始Pipeline推理"""
        if self.num_stages == 0:
            return False
        
        with self.lock:
            self.active_requests[request_id] = {
                "stage": 0,
                "input": input_data,
                "start_time": time.time(),
                "status": "running",
            }
        
        return True
    
    def advance_stage(self, request_id: str, stage_output: Any) -> int:
        """推进到下一阶段"""
        with self.lock:
            if request_id not in self.active_requests:
                return -1
            
            request = self.active_requests[request_id]
            current_stage = request["stage"]
            
            if current_stage >= self.num_stages - 1:
                # 最后阶段完成
                request["status"] = "completed"
                request["output"] = stage_output
                request["end_time"] = time.time()
                self.request_results[request_id] = request
                del self.active_requests[request_id]
                return -1
            
            # 推进到下一阶段
            request["stage"] = current_stage + 1
            request["input"] = stage_output
            
            return current_stage + 1
    
    def get_request_stage(self, request_id: str) -> int:
        """获取请求当前阶段"""
        with self.lock:
            if request_id in self.active_requests:
                return self.active_requests[request_id]["stage"]
        return -1
    
    def get_result(self, request_id: str) -> Optional[Dict]:
        """获取推理结果"""
        with self.lock:
            return self.request_results.get(request_id)
    
    def get_stage_node(self, stage_id: int) -> Optional[str]:
        """获取阶段对应的节点"""
        if stage_id in self.stages:
            return self.stages[stage_id].shard.node_id
        return None


# ==================== 分布式推理引擎 ====================

class DistributedInferenceEngine:
    """分布式推理引擎"""
    
    def __init__(self, model_name: str):
        self.model_name = model_name
        self.sharding_manager = ShardingManager(model_name)
        self.pipeline_coordinator: Optional[PipelineCoordinator] = None
        
        # 本地模型（如果是数据并行）
        self.local_model = None
        self.local_tokenizer = None
        
        # 状态
        self.initialized = False
        self.is_leader = False
    
    def initialize(self, nodes_info: Dict[str, Dict], is_leader: bool = False) -> bool:
        """初始化分布式推理"""
        self.is_leader = is_leader
        
        # 规划分片
        shards = self.sharding_manager.plan_sharding(nodes_info)
        if not shards:
            print("[分布式] 分片规划失败")
            return False
        
        # 创建Pipeline协调器
        self.pipeline_coordinator = PipelineCoordinator(shards)
        
        self.initialized = True
        print(f"[分布式] 初始化完成，策略: {self.sharding_manager.strategy.value}")
        return True
    
    def assign_shards(self, nodes_info: Dict[str, Dict]) -> Dict[str, int]:
        """分配分片"""
        return self.sharding_manager.assign_shards(nodes_info)
    
    def get_shard_info(self, node_id: str) -> Optional[Dict]:
        """获取节点的分片信息"""
        shard = self.sharding_manager.get_shard_for_node(node_id)
        if shard:
            return shard.to_dict()
        return None
    
    def submit_inference(self, request_id: str, prompt: str) -> bool:
        """提交推理请求"""
        if not self.pipeline_coordinator:
            return False
        
        return self.pipeline_coordinator.start_inference(request_id, prompt)
    
    def get_next_stage(self, request_id: str) -> Tuple[int, Optional[str]]:
        """获取下一阶段"""
        if not self.pipeline_coordinator:
            return -1, None
        
        stage = self.pipeline_coordinator.get_request_stage(request_id)
        if stage < 0:
            return -1, None
        
        node = self.pipeline_coordinator.get_stage_node(stage)
        return stage, node
    
    def complete_stage(self, request_id: str, stage_output: Any) -> int:
        """完成当前阶段"""
        if not self.pipeline_coordinator:
            return -1
        
        return self.pipeline_coordinator.advance_stage(request_id, stage_output)
    
    def get_result(self, request_id: str) -> Optional[Dict]:
        """获取推理结果"""
        if not self.pipeline_coordinator:
            return None
        
        return self.pipeline_coordinator.get_result(request_id)
    
    def get_status(self) -> Dict:
        """获取状态"""
        return {
            "model_name": self.model_name,
            "strategy": self.sharding_manager.strategy.value,
            "num_shards": len(self.sharding_manager.shards),
            "shards": [s.to_dict() for s in self.sharding_manager.shards],
            "initialized": self.initialized,
            "is_leader": self.is_leader,
        }


# ==================== 模型分片加载器 ====================

class ModelShardLoader:
    """模型分片加载器 - 只加载指定层"""
    
    def __init__(self, model_name: str, shard_info: Dict):
        self.model_name = model_name
        self.shard_info = shard_info
        
        self.shard_id = shard_info.get("shard_id", 0)
        self.layer_start = shard_info.get("layer_start", 0)
        self.layer_end = shard_info.get("layer_end", 0)
        self.has_embedding = shard_info.get("has_embedding", False)
        self.has_output = shard_info.get("has_output", False)
        
        # 模型组件
        self.config = None
        self.tokenizer = None
        self.embed_tokens = None
        self.layers = None
        self.norm = None
        self.lm_head = None
        
        self.loaded = False
    
    def load(self) -> bool:
        """加载模型分片"""
        if not HAS_TORCH:
            print("[分片加载] PyTorch未安装")
            return False
        
        try:
            print(f"[分片加载] 加载分片 {self.shard_id}")
            print(f"   层范围: {self.layer_start}-{self.layer_end}")
            print(f"   包含Embedding: {self.has_embedding}")
            print(f"   包含Output: {self.has_output}")
            
            # 加载配置
            self.config = AutoConfig.from_pretrained(self.model_name)
            
            # 加载tokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.model_name,
                trust_remote_code=True
            )
            
            # 加载完整模型
            print("   [1/3] 加载完整模型...")
            full_model = AutoModelForCausalLM.from_pretrained(
                self.model_name,
                torch_dtype=torch.float32,
                trust_remote_code=True,
                low_cpu_mem_usage=True
            )
            
            # 获取基础模型
            if hasattr(full_model, 'model'):
                base_model = full_model.model
            else:
                base_model = full_model
            
            # 提取组件
            print("   [2/3] 提取分片组件...")
            
            # Embedding
            if self.has_embedding:
                if hasattr(base_model, 'embed_tokens'):
                    self.embed_tokens = base_model.embed_tokens
                elif hasattr(base_model, 'wte'):
                    self.embed_tokens = base_model.wte
                print("      Embedding: 已加载")
            
            # Transformer层
            if hasattr(base_model, 'layers'):
                all_layers = list(base_model.layers)
            elif hasattr(base_model, 'h'):
                all_layers = list(base_model.h)
            else:
                all_layers = []
            
            self.layers = nn.ModuleList(all_layers[self.layer_start:self.layer_end + 1])
            print(f"      Transformer层: {len(self.layers)}层")
            
            # Output
            if self.has_output:
                if hasattr(base_model, 'norm'):
                    self.norm = base_model.norm
                if hasattr(full_model, 'lm_head'):
                    self.lm_head = full_model.lm_head
                print("      Output: 已加载")
            
            # 删除完整模型
            del full_model
            del all_layers
            
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            
            import gc
            gc.collect()
            
            self.loaded = True
            print(f"[分片加载] 分片 {self.shard_id} 加载完成")
            
            return True
            
        except Exception as e:
            print(f"[分片加载] 加载失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def forward_first(self, input_ids: torch.Tensor) -> torch.Tensor:
        """第一阶段前向传播（包含embedding）"""
        if not self.has_embedding:
            raise ValueError("此分片不包含embedding层")
        
        with torch.no_grad():
            hidden_states = self.embed_tokens(input_ids)
            
            for layer in self.layers:
                hidden_states = layer(hidden_states)[0]
            
            return hidden_states
    
    def forward_middle(self, hidden_states: torch.Tensor) -> torch.Tensor:
        """中间阶段前向传播"""
        with torch.no_grad():
            for layer in self.layers:
                hidden_states = layer(hidden_states)[0]
            return hidden_states
    
    def forward_last(self, hidden_states: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """最后阶段前向传播（包含output）"""
        if not self.has_output:
            raise ValueError("此分片不包含output层")
        
        with torch.no_grad():
            for layer in self.layers:
                hidden_states = layer(hidden_states)[0]
            
            if self.norm:
                hidden_states = self.norm(hidden_states)
            
            if self.lm_head:
                logits = self.lm_head(hidden_states)
                return logits, hidden_states
            
            return hidden_states, hidden_states
    
    def generate_token(self, logits: torch.Tensor) -> Tuple[int, str]:
        """从logits生成下一个token"""
        next_token_logits = logits[:, -1, :]
        next_token_id = next_token_logits.argmax(dim=-1).item()
        token_text = self.tokenizer.decode([next_token_id])
        return next_token_id, token_text


# ==================== 主函数 ====================

def main():
    """测试分布式推理模块"""
    print("="*60)
    print("  分布式大模型推理 - 联合分布式推理模块测试")
    print("="*60)
    
    # 测试模型分析
    model_name = "Qwen/Qwen2.5-0.5B-Instruct"
    
    print(f"\n[测试] 分析模型: {model_name}")
    model_info = ModelAnalyzer.analyze_model(model_name)
    
    if "error" in model_info:
        print(f"  错误: {model_info['error']}")
    else:
        print(f"  层数: {model_info.get('num_layers', 0)}")
        print(f"  隐藏层大小: {model_info.get('hidden_size', 0)}")
        print(f"  估计大小(FP16): {model_info.get('estimated_size_fp16', 0):.2f}GB")
    
    # 测试分片规划
    print(f"\n[测试] 规划分片...")
    
    # 模拟节点
    nodes_info = {
        "node1": {"memory_available_gb": 4.0, "cpu_cores": 4},
        "node2": {"memory_available_gb": 4.0, "cpu_cores": 4},
    }
    
    engine = DistributedInferenceEngine(model_name)
    engine.initialize(nodes_info, is_leader=True)
    
    print(f"\n[测试] 分片状态:")
    status = engine.get_status()
    for shard in status["shards"]:
        print(f"  分片{shard['shard_id']}: 层{shard['layer_start']}-{shard['layer_end']}, "
              f"大小{shard['size_gb']:.2f}GB")
    
    print("\n[测试] 完成")


if __name__ == "__main__":
    main()
