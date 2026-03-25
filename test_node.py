#!/usr/bin/env python3
"""简单测试脚本 - 验证节点基本功能"""

import sys
import os

# 设置UTF-8编码
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

print("=" * 60)
print("  分布式推理系统 - 功能测试")
print("=" * 60)

# 测试1: 导入依赖
print("\n[测试1] 检查依赖...")
try:
    import torch
    print(f"  - torch: {torch.__version__}")
    import transformers
    print(f"  - transformers: {transformers.__version__}")
    import psutil
    print(f"  - psutil: {psutil.__version__}")
    print("[OK] 依赖检查通过")
except ImportError as e:
    print(f"[ERROR] 缺少依赖: {e}")
    sys.exit(1)

# 测试2: 检查GPU
print("\n[测试2] 检查设备...")
if torch.cuda.is_available():
    print(f"  - GPU: {torch.cuda.get_device_name(0)}")
    print(f"  - 显存: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f}GB")
    device = "cuda"
else:
    print("  - 未检测到GPU，使用CPU")
    device = "cpu"

# 测试3: 导入主程序模块
print("\n[测试3] 导入主模块...")
try:
    # 添加路径
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'download'))
    
    # 动态导入
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "node_unified_complete", 
        os.path.join(os.path.dirname(__file__), 'download', 'node_unified_complete.py')
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    
    print(f"  - 版本: {module.VERSION}")
    print("[OK] 模块导入成功")
except Exception as e:
    print(f"[ERROR] 模块导入失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 测试4: 测试配置加载
print("\n[测试4] 测试配置加载...")
try:
    config_dict = module.load_config_file("config.json")
    print(f"  - 节点端口: {config_dict.get('node', {}).get('port', 5000)}")
    print(f"  - API端口: {config_dict.get('node', {}).get('api_port', 8080)}")
    print(f"  - 模型: {config_dict.get('model', {}).get('name', 'N/A')}")
    print(f"  - 并行模式: {config_dict.get('parallel', {}).get('mode', 'data_parallel')}")
    print("[OK] 配置加载成功")
except Exception as e:
    print(f"[ERROR] 配置加载失败: {e}")
    import traceback
    traceback.print_exc()

# 测试5: 测试模型下载/加载（使用小模型）
print("\n[测试5] 测试模型加载 (Qwen/Qwen2.5-0.5B-Instruct)...")
try:
    from transformers import AutoTokenizer, AutoModelForCausalLM
    import time
    
    model_name = "Qwen/Qwen2.5-0.5B-Instruct"
    print(f"  - 加载模型: {model_name}")
    print("  - 这可能需要几分钟（首次会下载模型）...")
    
    start = time.time()
    tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        model_name, 
        trust_remote_code=True,
        torch_dtype="auto",
        device_map="auto" if device == "cuda" else None
    )
    load_time = time.time() - start
    
    print(f"  - 加载时间: {load_time:.1f}秒")
    print("[OK] 模型加载成功")
except Exception as e:
    print(f"[ERROR] 模型加载失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 测试6: 测试推理
print("\n[测试6] 测试推理...")
try:
    prompt = "你好"
    inputs = tokenizer(prompt, return_tensors="pt")
    if device == "cuda":
        inputs = inputs.to(device)
    
    print(f"  - 输入: {prompt}")
    outputs = model.generate(**inputs, max_new_tokens=20)
    response = tokenizer.decode(outputs[0], skip_special_tokens=True)
    
    print(f"  - 输出: {response}")
    print("[OK] 推理测试成功")
except Exception as e:
    print(f"[ERROR] 推理测试失败: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("  所有测试完成!")
print("=" * 60)
