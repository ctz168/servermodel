#!/usr/bin/env python3
"""
木桶效应解决方案 - 动态负载均衡与慢节点检测

解决分布式推理系统中的木桶效应问题：
1. 动态负载均衡 - 根据节点性能自适应调整权重
2. 慢节点检测 - 自动识别和隔离性能差的节点
3. Pipeline 阶段均衡 - 动态调整 Pipeline 各阶段的负载
4. 自适应请求路由 - 智能分配请求到最佳节点

使用方法：
    from bucket_effect_solution import AdaptiveRequestRouter
    
    router = AdaptiveRequestRouter()
    
    # 路由请求
    best_node = router.route_request(request, nodes_info)
    
    # 记录结果
    router.record_result(node_id, latency, success)
"""

import time
import random
import threading
from typing import Dict, List, Optional, Tuple, Any
from collections import defaultdict, deque
from dataclasses import dataclass, field
import statistics


@dataclass
class NodePerformance:
    """节点性能记录"""
    node_id: str
    latencies: deque = field(default_factory=lambda: deque(maxlen=100))
    successes: deque = field(default_factory=lambda: deque(maxlen=100))
    last_update: float = 0.0
    
    # 计算指标
    avg_latency: float = 0.0
    success_rate: float = 1.0
    weight: float = 1.0
    
    def update(self, latency: float, success: bool):
        """更新性能记录"""
        self.latencies.append(latency)
        self.successes.append(1.0 if success else 0.0)
        self.last_update = time.time()
        
        # 计算平均延迟
        if self.latencies:
            self.avg_latency = statistics.mean(self.latencies)
        
        # 计算成功率
        if self.successes:
            self.success_rate = statistics.mean(self.successes)
        
        # 计算权重
        self._calculate_weight()
    
    def _calculate_weight(self):
        """计算权重"""
        if self.avg_latency <= 0:
            self.weight = 1.0
            return
        
        # 基准延迟 200ms
        baseline_latency = 0.2
        
        # 权重 = 成功率 / (延迟比例 + 0.1)
        latency_ratio = self.avg_latency / baseline_latency
        self.weight = self.success_rate / (latency_ratio + 0.1)
        
        # 限制权重范围
        self.weight = max(0.1, min(3.0, self.weight))


class DynamicLoadBalancer:
    """动态负载均衡器"""
    
    def __init__(self, baseline_latency: float = 0.2):
        self.baseline_latency = baseline_latency
        self.node_performances: Dict[str, NodePerformance] = {}
        self.lock = threading.Lock()
        
    def update_node_performance(self, node_id: str, latency: float, success: bool):
        """更新节点性能"""
        with self.lock:
            if node_id not in self.node_performances:
                self.node_performances[node_id] = NodePerformance(node_id=node_id)
            
            self.node_performances[node_id].update(latency, success)
    
    def get_node_weight(self, node_id: str) -> float:
        """获取节点权重"""
        with self.lock:
            if node_id in self.node_performances:
                return self.node_performances[node_id].weight
            return 1.0
    
    def get_all_weights(self) -> Dict[str, float]:
        """获取所有节点权重"""
        with self.lock:
            return {
                node_id: perf.weight 
                for node_id, perf in self.node_performances.items()
            }
    
    def select_best_node(self, candidate_nodes: List[str], 
                         exclude_nodes: set = None) -> Optional[str]:
        """选择最佳节点"""
        exclude_nodes = exclude_nodes or set()
        
        with self.lock:
            valid_nodes = [
                n for n in candidate_nodes 
                if n not in exclude_nodes and n in self.node_performances
            ]
            
            if not valid_nodes:
                # 没有历史数据，随机选择
                remaining = [n for n in candidate_nodes if n not in exclude_nodes]
                return random.choice(remaining) if remaining else None
            
            # 选择权重最高的节点
            return max(valid_nodes, key=lambda n: self.node_performances[n].weight)
    
    def weighted_random_select(self, candidate_nodes: List[str],
                               exclude_nodes: set = None) -> Optional[str]:
        """加权随机选择"""
        exclude_nodes = exclude_nodes or set()
        
        with self.lock:
            valid_nodes = [
                n for n in candidate_nodes 
                if n not in exclude_nodes
            ]
            
            if not valid_nodes:
                return None
            
            if len(valid_nodes) == 1:
                return valid_nodes[0]
            
            # 获取权重
            weights = []
            for node_id in valid_nodes:
                if node_id in self.node_performances:
                    weights.append(self.node_performances[node_id].weight)
                else:
                    weights.append(1.0)
            
            # 加权随机选择
            total_weight = sum(weights)
            r = random.uniform(0, total_weight)
            
            cumulative = 0
            for node_id, weight in zip(valid_nodes, weights):
                cumulative += weight
                if r <= cumulative:
                    return node_id
            
            return valid_nodes[-1]


class StragglerDetector:
    """慢节点检测器"""
    
    def __init__(self, 
                 threshold_factor: float = 2.0,
                 min_samples: int = 10,
                 recovery_threshold: float = 1.5):
        """
        初始化慢节点检测器
        
        Args:
            threshold_factor: 慢节点阈值（相对于中位数的倍数）
            min_samples: 最小样本数
            recovery_threshold: 恢复阈值
        """
        self.threshold_factor = threshold_factor
        self.min_samples = min_samples
        self.recovery_threshold = recovery_threshold
        
        self.node_latencies: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        self.straggler_nodes: set = set()
        self.lock = threading.Lock()
        
        # 统计
        self.detection_count = 0
        self.recovery_count = 0
    
    def record_latency(self, node_id: str, latency: float):
        """记录节点延迟"""
        with self.lock:
            self.node_latencies[node_id].append(latency)
            self._detect_stragglers()
    
    def _detect_stragglers(self):
        """检测慢节点"""
        if len(self.node_latencies) < 2:
            return
        
        # 计算所有节点的中位数延迟
        all_latencies = []
        for latencies in self.node_latencies.values():
            if len(latencies) >= self.min_samples:
                all_latencies.extend(list(latencies)[-20:])
        
        if len(all_latencies) < 10:
            return
        
        median_latency = statistics.median(all_latencies)
        threshold = median_latency * self.threshold_factor
        recovery_threshold = median_latency * self.recovery_threshold
        
        # 检测慢节点
        new_stragglers = set()
        for node_id, latencies in self.node_latencies.items():
            if len(latencies) < self.min_samples:
                continue
            
            recent_avg = statistics.mean(list(latencies)[-10:])
            
            # 已经是慢节点，检查是否恢复
            if node_id in self.straggler_nodes:
                if recent_avg <= recovery_threshold:
                    # 恢复正常
                    self.recovery_count += 1
                    print(f"[慢节点检测] ✅ 节点 {node_id[:8]} 已恢复正常")
                else:
                    new_stragglers.add(node_id)
            else:
                # 检查是否变成慢节点
                if recent_avg > threshold:
                    new_stragglers.add(node_id)
                    self.detection_count += 1
                    print(f"[慢节点检测] ⚠️ 发现慢节点 {node_id[:8]} (延迟: {recent_avg:.3f}s, 阈值: {threshold:.3f}s)")
        
        # 更新慢节点列表
        self.straggler_nodes = new_stragglers
    
    def is_straggler(self, node_id: str) -> bool:
        """判断是否是慢节点"""
        with self.lock:
            return node_id in self.straggler_nodes
    
    def get_stragglers(self) -> set:
        """获取所有慢节点"""
        with self.lock:
            return self.straggler_nodes.copy()
    
    def get_healthy_nodes(self, all_nodes: List[str]) -> List[str]:
        """获取健康节点列表"""
        with self.lock:
            return [n for n in all_nodes if n not in self.straggler_nodes]
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self.lock:
            return {
                "total_nodes": len(self.node_latencies),
                "straggler_count": len(self.straggler_nodes),
                "stragglers": list(self.straggler_nodes),
                "detection_count": self.detection_count,
                "recovery_count": self.recovery_count,
            }


class PipelineStageBalancer:
    """Pipeline 阶段均衡器"""
    
    def __init__(self, num_stages: int):
        self.num_stages = num_stages
        self.stage_latencies: Dict[int, deque] = defaultdict(lambda: deque(maxlen=100))
        self.optimal_distribution: Optional[Dict[int, float]] = None
        self.lock = threading.Lock()
        
    def record_stage_latency(self, stage_id: int, latency: float):
        """记录阶段延迟"""
        with self.lock:
            self.stage_latencies[stage_id].append(latency)
            
            # 定期重新计算最优分布
            if len(self.stage_latencies[stage_id]) % 10 == 0:
                self._recalculate_distribution()
    
    def _recalculate_distribution(self):
        """重新计算最优层分布"""
        avg_latencies = {}
        
        for stage_id, latencies in self.stage_latencies.items():
            if len(latencies) >= 5:
                avg_latencies[stage_id] = statistics.mean(list(latencies)[-20:])
        
        if len(avg_latencies) < 2:
            return
        
        # 目标：使所有阶段的延迟接近
        target_latency = statistics.mean(avg_latencies.values())
        
        # 计算每个阶段应该处理的层数比例
        layer_distribution = {}
        total_ratio = 0
        
        for stage_id, latency in avg_latencies.items():
            # 延迟越高，比例越低
            ratio = target_latency / (latency + 0.001)
            layer_distribution[stage_id] = ratio
            total_ratio += ratio
        
        # 归一化
        if total_ratio > 0:
            self.optimal_distribution = {
                stage_id: ratio / total_ratio 
                for stage_id, ratio in layer_distribution.items()
            }
            
            print(f"[Pipeline均衡] 层分布建议: {self.optimal_distribution}")
    
    def suggest_layer_redistribution(self, current_layers: Dict[int, int]) -> Dict[int, int]:
        """建议层重分布"""
        with self.lock:
            if not self.optimal_distribution:
                return current_layers
            
            total_layers = sum(current_layers.values())
            new_distribution = {}
            
            for stage_id in range(self.num_stages):
                if stage_id in self.optimal_distribution:
                    ratio = self.optimal_distribution[stage_id]
                    new_distribution[stage_id] = max(1, int(total_layers * ratio))
                else:
                    new_distribution[stage_id] = current_layers.get(stage_id, 1)
            
            # 确保总层数一致
            diff = total_layers - sum(new_distribution.values())
            if diff != 0:
                # 将差异加到延迟最低的阶段
                if self.optimal_distribution:
                    fastest_stage = max(self.optimal_distribution, 
                                       key=self.optimal_distribution.get)
                    new_distribution[fastest_stage] += diff
            
            return new_distribution
    
    def get_stage_efficiency(self) -> float:
        """获取 Pipeline 效率"""
        with self.lock:
            avg_latencies = {}
            for stage_id, latencies in self.stage_latencies.items():
                if latencies:
                    avg_latencies[stage_id] = statistics.mean(list(latencies)[-20:])
            
            if len(avg_latencies) < 2:
                return 1.0
            
            min_latency = min(avg_latencies.values())
            max_latency = max(avg_latencies.values())
            
            if max_latency == 0:
                return 1.0
            
            return min_latency / max_latency


class AdaptiveRequestRouter:
    """自适应请求路由器"""
    
    def __init__(self, 
                 baseline_latency: float = 0.2,
                 straggler_threshold: float = 2.0):
        """
        初始化自适应请求路由器
        
        Args:
            baseline_latency: 基准延迟（秒）
            straggler_threshold: 慢节点阈值
        """
        self.load_balancer = DynamicLoadBalancer(baseline_latency)
        self.straggler_detector = StragglerDetector(straggler_threshold)
        self.pipeline_balancer: Optional[PipelineStageBalancer] = None
        
        self.lock = threading.Lock()
        
        # 统计
        self.total_requests = 0
        self.successful_requests = 0
    
    def set_pipeline_stages(self, num_stages: int):
        """设置 Pipeline 阶段数"""
        self.pipeline_balancer = PipelineStageBalancer(num_stages)
    
    def route_request(self, 
                      nodes_info: Dict[str, Any],
                      mode: str = "data_parallel") -> Optional[str]:
        """
        路由请求到最佳节点
        
        Args:
            nodes_info: 节点信息字典
            mode: 路由模式 (data_parallel, pipeline_parallel)
            
        Returns:
            最佳节点 ID
        """
        self.total_requests += 1
        
        # 获取健康节点
        all_nodes = list(nodes_info.keys())
        healthy_nodes = self.straggler_detector.get_healthy_nodes(all_nodes)
        
        if not healthy_nodes:
            # 所有节点都是慢节点，使用全部节点
            healthy_nodes = all_nodes
        
        if not healthy_nodes:
            return None
        
        if mode == "data_parallel":
            # 数据并行：加权随机选择
            return self.load_balancer.weighted_random_select(healthy_nodes)
        
        elif mode == "pipeline_parallel":
            # Pipeline 并行：选择入口节点
            return self._select_pipeline_entry(healthy_nodes, nodes_info)
        
        return random.choice(healthy_nodes)
    
    def _select_pipeline_entry(self, 
                               nodes: List[str],
                               nodes_info: Dict[str, Any]) -> Optional[str]:
        """选择 Pipeline 入口节点"""
        # 找到第一个阶段的节点
        entry_nodes = []
        for node_id in nodes:
            node = nodes_info.get(node_id)
            if node and hasattr(node, 'model_shard_id') and node.model_shard_id == 0:
                entry_nodes.append(node_id)
        
        if not entry_nodes:
            return random.choice(nodes) if nodes else None
        
        # 加权选择
        return self.load_balancer.weighted_random_select(entry_nodes)
    
    def record_result(self, 
                      node_id: str, 
                      latency: float, 
                      success: bool,
                      stage_id: Optional[int] = None):
        """
        记录请求结果
        
        Args:
            node_id: 节点 ID
            latency: 延迟（秒）
            success: 是否成功
            stage_id: Pipeline 阶段 ID（可选）
        """
        # 更新负载均衡器
        self.load_balancer.update_node_performance(node_id, latency, success)
        
        # 更新慢节点检测器
        self.straggler_detector.record_latency(node_id, latency)
        
        # 更新 Pipeline 均衡器
        if stage_id is not None and self.pipeline_balancer:
            self.pipeline_balancer.record_stage_latency(stage_id, latency)
        
        # 更新统计
        if success:
            self.successful_requests += 1
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "success_rate": self.successful_requests / max(1, self.total_requests),
            "node_weights": self.load_balancer.get_all_weights(),
            "straggler_stats": self.straggler_detector.get_stats(),
            "pipeline_efficiency": self.pipeline_balancer.get_stage_efficiency() if self.pipeline_balancer else None,
        }
    
    def get_recommendations(self) -> List[str]:
        """获取优化建议"""
        recommendations = []
        
        stats = self.get_stats()
        
        # 检查成功率
        if stats["success_rate"] < 0.9:
            recommendations.append(f"⚠️ 成功率较低 ({stats['success_rate']:.1%})，建议检查节点健康状态")
        
        # 检查慢节点
        straggler_count = stats["straggler_stats"]["straggler_count"]
        if straggler_count > 0:
            recommendations.append(f"⚠️ 发现 {straggler_count} 个慢节点，建议检查或隔离")
        
        # 检查 Pipeline 效率
        if stats["pipeline_efficiency"] is not None and stats["pipeline_efficiency"] < 0.5:
            recommendations.append(f"⚠️ Pipeline 效率较低 ({stats['pipeline_efficiency']:.1%})，建议重新分配层")
        
        # 检查权重差异
        weights = list(stats["node_weights"].values())
        if weights and max(weights) / min(weights) > 3:
            recommendations.append("⚠️ 节点性能差异较大，建议升级或替换慢节点")
        
        return recommendations


# 使用示例
if __name__ == "__main__":
    print("=" * 60)
    print("木桶效应解决方案示例")
    print("=" * 60)
    
    # 创建路由器
    router = AdaptiveRequestRouter(baseline_latency=0.2, straggler_threshold=2.0)
    
    # 模拟节点
    nodes = {
        "node-a": {"health_score": 100, "active_tasks": 0},
        "node-b": {"health_score": 80, "active_tasks": 1},
        "node-c": {"health_score": 60, "active_tasks": 2},
    }
    
    print("\n【测试1】正常请求路由:")
    for i in range(10):
        best_node = router.route_request(nodes, mode="data_parallel")
        print(f"  请求 {i+1}: 路由到 {best_node}")
        
        # 模拟结果
        latency = random.uniform(0.1, 0.3)
        success = random.random() > 0.1
        router.record_result(best_node, latency, success)
    
    print("\n【测试2】模拟慢节点:")
    # 模拟 node-c 变慢
    for i in range(20):
        router.record_result("node-c", random.uniform(0.5, 1.0), True)
    
    print("\n【测试3】慢节点检测后路由:")
    for i in range(5):
        best_node = router.route_request(nodes, mode="data_parallel")
        print(f"  请求 {i+1}: 路由到 {best_node}")
    
    print("\n【统计信息】")
    stats = router.get_stats()
    print(f"  总请求数: {stats['total_requests']}")
    print(f"  成功率: {stats['success_rate']:.1%}")
    print(f"  节点权重: {stats['node_weights']}")
    print(f"  慢节点: {stats['straggler_stats']['stragglers']}")
    
    print("\n【优化建议】")
    for rec in router.get_recommendations():
        print(f"  {rec}")
