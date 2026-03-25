#!/usr/bin/env python3
"""快速功能验证测试"""

import sys
import os

print("=" * 60)
print("  快速功能验证")
print("=" * 60)

# 测试1: 依赖检查
print("\n[1] 依赖检查...")
try:
    import torch
    print(f"    torch: {torch.__version__}")
    import transformers
    print(f"    transformers: {transformers.__version__}")
    import psutil
    print(f"    psutil: {psutil.__version__}")
    import requests
    print(f"    requests: {requests.__version__}")
    print("    [OK]")
except ImportError as e:
    print(f"    [ERROR] {e}")
    sys.exit(1)

# 测试2: 设备检查
print("\n[2] 设备检查...")
if torch.cuda.is_available():
    print(f"    GPU: {torch.cuda.get_device_name(0)}")
    print(f"    显存: {torch.cuda.get_device_properties(0).total_memory // 1024**3}GB")
else:
    print("    使用CPU")

# 测试3: 模块导入
print("\n[3] 模块导入...")
try:
    spec = __import__('importlib.util').util.spec_from_file_location(
        "node_unified_complete", 
        "download/node_unified_complete.py"
    )
    module = __import__('importlib.util').util.module_from_spec(spec)
    spec.loader.exec_module(module)
    print(f"    版本: {module.VERSION}")
    print("    [OK]")
except Exception as e:
    print(f"    [ERROR] {e}")
    sys.exit(1)

# 测试4: 配置文件
print("\n[4] 配置文件...")
try:
    with open("config.json", "r", encoding="utf-8") as f:
        import json
        config = json.load(f)
    print(f"    节点端口: {config['node']['port']}")
    print(f"    API端口: {config['node']['api_port']}")
    print(f"    模型: {config['model']['name']}")
    print("    [OK]")
except Exception as e:
    print(f"    [ERROR] {e}")

# 测试5: 简单推理测试
print("\n[5] 简单推理测试 (Qwen/Qwen2.5-0.5B-Instruct)...")
try:
    from transformers import AutoTokenizer, AutoModelForCausalLM
    import time
    
    start = time.time()
    tokenizer = AutoTokenizer.from_pretrained(
        "Qwen/Qwen2.5-0.5B-Instruct", 
        trust_remote_code=True
    )
    model = AutoModelForCausalLM.from_pretrained(
        "Qwen/Qwen2.5-0.5B-Instruct",
        trust_remote_code=True,
        torch_dtype="auto"
    )
    
    inputs = tokenizer("你好", return_tensors="pt")
    outputs = model.generate(**inputs, max_new_tokens=10)
    response = tokenizer.decode(outputs[0], skip_special_tokens=True)
    
    print(f"    加载+推理时间: {time.time()-start:.1f}s")
    print(f"    输入: '你好'")
    print(f"    输出: '{response}'")
    print("    [OK]")
except Exception as e:
    print(f"    [ERROR] {e}")

print("\n" + "=" * 60)
print("  测试完成!")
print("=" * 60)
