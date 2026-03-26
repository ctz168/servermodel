#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
启动命令生成器
根据节点配置生成相应的启动命令
"""

import argparse


def generate_commands():
    """生成启动命令"""
    
    print("\n" + "="*70)
    print("  4节点集群启动命令生成器")
    print("="*70)
    
    print("""
请输入以下信息:
""")

    # 获取 ngrok token
    ngrok_token = input("Ngrok Token (从 https://dashboard.ngrok.com 获取): ").strip()
    
    if not ngrok_token:
        print("\n错误: Ngrok Token 不能为空")
        return
    
    # 获取模型选择
    print("\n选择模型:")
    print("  1. Qwen2.5-3B-Instruct  (适合数据并行)")
    print("  2. Qwen2.5-7B-Instruct  (推荐，适合混合并行)")
    print("  3. Qwen2.5-14B-Instruct (需要4节点Pipeline)")
    
    model_choice = input("请选择 [1/2/3，默认2]: ").strip() or "2"
    
    models = {
        "1": "Qwen/Qwen2.5-3B-Instruct",
        "2": "Qwen/Qwen2.5-7B-Instruct",
        "3": "Qwen/Qwen2.5-14B-Instruct"
    }
    model = models.get(model_choice, models["2"])
    
    # 生成命令
    print("\n" + "="*70)
    print("  生成的启动命令")
    print("="*70)
    
    if model_choice in ["1", "2"]:
        # 数据并行 或 混合并行 (2x2)
        
        # 云主机1
        print("\n[云主机1 - Pipeline组A 领导节点]")
        print("-"*70)
        print("""
# Linux
cd ~/servermodel
source venv/bin/activate
export HF_ENDPOINT=https://hf-mirror.com

python core/node_unified_complete.py \\
    --mode pipeline_parallel \\
    --stages 2 \\
    --port 5000 \\
    --api-port 8080 \\
    --model "{model}" \\
    --ngrok \\
    --ngrok-auth-token {token}
""".format(model=model, token=ngrok_token))
        
        # 云主机2
        print("\n[云主机2 - Pipeline组B 领导节点]")
        print("-"*70)
        print("""
# Linux
cd ~/servermodel
source venv/bin/activate
export HF_ENDPOINT=https://hf-mirror.com

python core/node_unified_complete.py \\
    --mode pipeline_parallel \\
    --stages 2 \\
    --port 5000 \\
    --api-port 8080 \\
    --model "{model}" \\
    --ngrok \\
    --ngrok-auth-token {token}
""".format(model=model, token=ngrok_token))
        
        print("\n" + "="*70)
        print("  重要: 请记录上面两台云主机输出的 Ngrok 地址!")
        print("  例如: tcp://0.tcp.ngrok.io:12345")
        print("="*70)
        
        # 获取 ngrok 地址
        ngrok1 = input("\n云主机1 的 Ngrok 地址 (如 0.tcp.ngrok.io:12345): ").strip()
        ngrok2 = input("云主机2 的 Ngrok 地址 (如 0.tcp.ngrok.io:67890): ").strip()
        
        # 本地Windows1
        print("\n[本地Windows1 - Pipeline组A 工作节点]")
        print("-"*70)
        print("""
# Windows PowerShell
cd c:\\Users\\Administrator\\Desktop\\servermodel
.\\venv\\Scripts\\activate
$env:HF_ENDPOINT = "https://hf-mirror.com"

python core/node_unified_complete.py `
    --mode pipeline_parallel `
    --stages 2 `
    --seeds "{ngrok}" `
    --model "{model}"
""".format(model=model, ngrok=ngrok1))
        
        # 本地Windows2
        print("\n[本地Windows2 - Pipeline组B 工作节点]")
        print("-"*70)
        print("""
# Windows PowerShell
cd c:\\Users\\Administrator\\Desktop\\servermodel
.\\venv\\Scripts\\activate
$env:HF_ENDPOINT = "https://hf-mirror.com"

python core/node_unified_complete.py `
    --mode pipeline_parallel `
    --stages 2 `
    --seeds "{ngrok}" `
    --model "{model}"
""".format(model=model, ngrok=ngrok2))
    
    else:
        # 4节点 Pipeline
        print("\n[4节点 Pipeline 模式]")
        print("需要逐级连接，请按顺序启动节点...\n")
        
        # 云主机1
        print("[云主机1 - 阶段0]")
        print("-"*70)
        print("""python core/node_unified_complete.py \\
    --mode pipeline_parallel \\
    --stages 4 \\
    --port 5000 \\
    --model "{model}" \\
    --ngrok --ngrok-auth-token {token}
""".format(model=model, token=ngrok_token))
        
        ngrok1 = input("\n云主机1 的 Ngrok 地址: ").strip()
        
        # 云主机2
        print("\n[云主机2 - 阶段1]")
        print("-"*70)
        print("""python core/node_unified_complete.py \\
    --mode pipeline_parallel \\
    --stages 4 \\
    --seeds "{ngrok}" \\
    --ngrok --ngrok-auth-token {token}
""".format(model=model, ngrok=ngrok1, token=ngrok_token))
        
        ngrok2 = input("\n云主机2 的 Ngrok 地址: ").strip()
        
        # 本地Windows1
        print("\n[本地Windows1 - 阶段2]")
        print("-"*70)
        print("""python core/node_unified_complete.py `
    --mode pipeline_parallel `
    --stages 4 `
    --seeds "{ngrok}"
""".format(ngrok=ngrok2))
        
        # 本地Windows2
        print("\n[本地Windows2 - 阶段3]")
        print("-"*70)
        print("""python core/node_unified_complete.py `
    --mode pipeline_parallel `
    --stages 4 `
    --seeds "本地Windows1_IP:5000"
""")
    
    print("\n" + "="*70)
    print("  启动顺序")
    print("="*70)
    print("""
  1. 先启动云主机1，等待显示 Ngrok 地址
  2. 再启动云主机2，等待显示 Ngrok 地址
  3. 然后启动本地Windows1，使用云主机1的地址
  4. 最后启动本地Windows2，使用云主机2的地址

  测试 API:
  curl -X POST http://云主机IP:8080/v1/chat/completions \\
    -H "Content-Type: application/json" \\
    -d '{{"model": "{model}", "messages": [{{"role": "user", "content": "你好"}}]}}'
""".format(model=model))


if __name__ == "__main__":
    try:
        generate_commands()
    except KeyboardInterrupt:
        print("\n\n已取消")
