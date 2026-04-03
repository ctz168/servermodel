#!/usr/bin/env python3
"""
Pipeline 切片实验 v3 - 使用 DynamicCache 实现 Pipeline 并行

核心: 用 transformers 的 DynamicCache 管理 KV Cache，
把 Qwen2.5-0.5B (24层) 掰成两半:
  Stage 0: embed + rotary + layers 0-11
  Stage 1: layers 12-23 + norm + lm_head
"""

import os
import sys
import time
import torch
import json
import gc

os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
os.environ['TRANSFORMERS_VERBOSITY'] = 'error'

from transformers import AutoModelForCausalLM, AutoTokenizer, AutoConfig, DynamicCache

MODEL_NAME = "Qwen/Qwen2.5-0.5B-Instruct"
PROMPT = "你好，请介绍一下你自己"
MAX_NEW_TOKENS = 30

def print_sep(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def run_stage_prefill(layers, hidden, position_ids, position_embeddings, cache, layer_offset, causal_mask=None):
    """
    Prefill: 处理完整 prompt sequence
    
    Args:
        layers: 该阶段的层列表
        hidden: (1, seq, dim)
        position_ids: (1, seq)
        position_embeddings: (cos, sin) from rotary_emb
        cache: DynamicCache
        layer_offset: 该阶段的第一层在完整模型中的索引
        causal_mask: optional causal attention mask
    Returns:
        hidden: (1, seq, dim)
    """
    for i, layer in enumerate(layers):
        layer_idx = layer_offset + i
        kwargs = {
            "position_ids": position_ids,
            "position_embeddings": position_embeddings,
            "past_key_values": cache,
            "use_cache": True,
        }
        if causal_mask is not None:
            kwargs["attention_mask"] = causal_mask

        result = layer(hidden, **kwargs)

        # 在 transformers 5.x 中, layer 返回的可能是 tuple 或 BaseModelOutput
        if isinstance(result, tuple):
            hidden = result[0]
        elif hasattr(result, 'last_hidden_state'):
            hidden = result.last_hidden_state
        else:
            hidden = result
    return hidden


def run_stage_decode_one_token(layers, hidden_1token, position_id_1token, position_embeddings_1token, cache, layer_offset):
    """
    Decode: 处理1个新 token
    
    Args:
        layers: 该阶段的层列表
        hidden_1token: (1, 1, dim) - 新 token 的 hidden state
        position_id_1token: (1, 1) - 新 token 的位置
        position_embeddings_1token: (cos, sin)
        cache: DynamicCache (已包含历史 KV)
        layer_offset: 层偏移
    Returns:
        hidden: (1, 1, dim)
    """
    for i, layer in enumerate(layers):
        layer_idx = layer_offset + i
        result = layer(
            hidden_1token,
            position_ids=position_id_1token,
            position_embeddings=position_embeddings_1token,
            past_key_values=cache,
            use_cache=True,
        )
        if isinstance(result, tuple):
            hidden_1token = result[0]
        elif hasattr(result, 'last_hidden_state'):
            hidden_1token = result.last_hidden_state
        else:
            hidden_1token = result
    return hidden_1token


def make_causal_mask(seq_len, device):
    return torch.triu(
        torch.full((seq_len, seq_len), float('-inf'), device=device), diagonal=1
    ).unsqueeze(0).unsqueeze(0)


def full_inference(model, tokenizer, prompt, max_tokens=MAX_NEW_TOKENS):
    """完整模型推理（手动逐层，与Pipeline使用相同的代码路径）"""
    print("[完整模型推理 - 手动逐层]")
    inputs = tokenizer(prompt, return_tensors='pt')
    input_ids = inputs['input_ids']
    seq_len = input_ids.shape[1]

    t0 = time.time()
    
    # Prefill: 所有层
    cache = DynamicCache()
    hidden = model.model.embed_tokens(input_ids)
    position_ids = torch.arange(seq_len, device=hidden.device).unsqueeze(0)
    position_embeddings = model.model.rotary_emb(hidden, position_ids)
    
    for i in range(model.config.num_hidden_layers):
        hidden = model.model.layers[i](hidden, position_ids=position_ids,
                                        position_embeddings=position_embeddings,
                                        past_key_values=cache, use_cache=True)
        if hasattr(hidden, 'last_hidden_state'):
            hidden = hidden.last_hidden_state
        elif isinstance(hidden, tuple):
            hidden = hidden[0]
    
    hidden = model.model.norm(hidden)
    logits = model.lm_head(hidden[:, -1:, :])
    first_token = torch.argmax(logits[:, -1, :], dim=-1).item()
    generated = []
    if first_token != tokenizer.eos_token_id:
        generated.append(first_token)

    # Decode
    hidden_dim = model.config.hidden_size
    for step in range(max_tokens - 1):
        if not generated or len(generated) >= max_tokens:
            break
        tok = torch.tensor([[generated[-1]]])
        h = model.model.embed_tokens(tok)
        p = torch.tensor([[seq_len + step]])
        d = torch.zeros(1, 1, hidden_dim, dtype=model.dtype)
        pe = model.model.rotary_emb(d, p)
        for i in range(model.config.num_hidden_layers):
            h = model.model.layers[i](h, position_ids=p, position_embeddings=pe,
                                       past_key_values=cache, use_cache=True)
            if hasattr(h, 'last_hidden_state'):
                h = h.last_hidden_state
            elif isinstance(h, tuple):
                h = h[0]
        h = model.model.norm(h)
        l = model.lm_head(h)
        nt = torch.argmax(l[:, -1, :], dim=-1).item()
        if nt == tokenizer.eos_token_id:
            break
        generated.append(nt)

    elapsed = time.time() - t0
    resp = tokenizer.decode(generated, skip_special_tokens=True)
    print(f"  Token: {len(generated)}, 耗时: {elapsed:.3f}s, 回复: {resp}")
    return resp, elapsed


def pipeline_kv(model, tokenizer, prompt, num_stages=2, max_tokens=MAX_NEW_TOKENS, label="Pipeline"):
    """
    Pipeline 多阶段推理 + DynamicCache
    
    将 N 层分成 num_stages 份，用 DynamicCache 正确管理 KV cache
    """
    total_layers = model.config.num_hidden_layers
    layers_per_stage = total_layers // num_stages
    half = layers_per_stage

    stage_ranges = []
    for s in range(num_stages):
        s_start = s * layers_per_stage
        s_end = s_start + layers_per_stage if s < num_stages - 1 else total_layers
        stage_ranges.append((s_start, s_end))

    print(f"[{label}]")
    print(f"  {num_stages} 阶段 Pipeline:")
    for s, (ss, se) in enumerate(stage_ranges):
        extra = " + embed+rotary" if s == 0 else ""
        extra += " + norm+lm_head" if s == num_stages - 1 else ""
        print(f"    Stage {s}: layers {ss}-{se-1}{extra}")

    inputs = tokenizer(prompt, return_tensors='pt')
    input_ids = inputs['input_ids']
    seq_len = input_ids.shape[1]
    print(f"  Prompt token数: {seq_len}")

    t0 = time.time()

    # 共享的 DynamicCache (一个 cache 管理所有层的 KV)
    cache = DynamicCache()

    # ===== PREFILL =====
    # Stage 0: embed + rotary + layers 0..half-1
    hidden = model.model.embed_tokens(input_ids)
    position_ids = torch.arange(seq_len, device=hidden.device).unsqueeze(0)
    position_embeddings = model.model.rotary_emb(hidden, position_ids)
    stage0_layers = [model.model.layers[i] for i in range(stage_ranges[0][0], stage_ranges[0][1])]
    hidden = run_stage_prefill(
        stage0_layers, hidden, position_ids, position_embeddings,
        cache, stage_ranges[0][0]
    )

    # 传输
    xfer = hidden.nelement() * hidden.element_size() / (1024*1024)
    print(f"  [传输-Prefill] Stage 0 -> Stage 1: {xfer:.2f} MB")

    # Stage 1: layers half..total-1 + norm
    stage1_layers = [model.model.layers[i] for i in range(stage_ranges[1][0], stage_ranges[1][1])]
    hidden = run_stage_prefill(
        stage1_layers, hidden, position_ids, position_embeddings,
        cache, stage_ranges[1][0]
    )
    hidden = model.model.norm(hidden)

    # 第一个 token
    logits = model.lm_head(hidden[:, -1:, :])
    first_token = torch.argmax(logits[:, -1, :], dim=-1)

    generated = []
    if first_token.item() != tokenizer.eos_token_id:
        generated.append(first_token.item())

    # ===== DECODE =====
    cur_pos = seq_len
    n_decode_transfers = 0
    hidden_dim = model.config.hidden_size

    for t in range(max_tokens - 1):
        if not generated or len(generated) >= max_tokens:
            break

        new_token_id = generated[-1]

        # Stage 0: 1 token
        new_token_tensor = torch.tensor([[new_token_id]], device=hidden.device)
        new_embed = model.model.embed_tokens(new_token_tensor).to(model.dtype)
        new_pos = torch.tensor([[cur_pos]], device=hidden.device)
        dummy = torch.zeros(1, 1, hidden_dim, device=hidden.device, dtype=model.dtype)
        new_pe = model.model.rotary_emb(dummy, new_pos)

        s0_out = run_stage_decode_one_token(
            stage0_layers, new_embed, new_pos, new_pe, cache, stage_ranges[0][0]
        )
        n_decode_transfers += 1

        # Stage 1: 1 token
        s1_out = run_stage_decode_one_token(
            stage1_layers, s0_out, new_pos, new_pe, cache, stage_ranges[1][0]
        )
        s1_out = model.model.norm(s1_out)

        logits = model.lm_head(s1_out)
        next_token = torch.argmax(logits[:, -1, :], dim=-1)
        if next_token.item() == tokenizer.eos_token_id:
            break
        generated.append(next_token.item())
        cur_pos += 1

    elapsed = time.time() - t0
    resp = tokenizer.decode(generated, skip_special_tokens=True)
    print(f"  传输: 1 prefill + {n_decode_transfers} decode = {n_decode_transfers+1} 次")
    print(f"  Token: {len(generated)}, 耗时: {elapsed:.3f}s, 回复: {resp}")
    return resp, elapsed


def split_model_pipeline_kv(model, tokenizer, prompt, max_tokens=MAX_NEW_TOKENS):
    """
    真正的双分片模型 - 各自持有独立权重副本
    
    模拟两台不同的机器，各自只加载一半的模型参数
    """
    import copy
    total_layers = model.config.num_hidden_layers
    half = total_layers // 2

    print(f"[双分片独立模型]")
    print(f"  复制 Stage 0 权重 (layers 0-{half-1})...")
    s0_layers = [copy.deepcopy(model.model.layers[i]) for i in range(half)]
    for l in s0_layers:
        l.eval()
    s0_embed = model.model.embed_tokens
    s0_rotary = model.model.rotary_emb

    print(f"  复制 Stage 1 权重 (layers {half}-{total_layers-1})...")
    s1_layers = [copy.deepcopy(model.model.layers[i]) for i in range(half, total_layers)]
    for l in s1_layers:
        l.eval()
    s1_norm = copy.deepcopy(model.model.norm)
    s1_lm = copy.deepcopy(model.lm_head)

    # 确认独立
    p0_total = sum(sum(p.numel() for p in l.parameters()) for l in s0_layers) / 1e6
    p1_total = sum(sum(p.numel() for p in l.parameters()) for l in s1_layers) / 1e6
    p_lm = sum(p.numel() for p in s1_lm.parameters()) / 1e6
    p_norm = sum(p.numel() for p in s1_norm.parameters()) / 1e6
    print(f"  Stage 0: {p0_total:.1f}M + Stage 1: {p1_total:.1f}M + norm: {p_norm:.0f}K + lm_head: {p_lm:.1f}M")
    print(f"  总分片参数: {p0_total+p1_total+p_norm/1e3+p_lm:.1f}M")

    inputs = tokenizer(prompt, return_tensors='pt')
    input_ids = inputs['input_ids']
    seq_len = input_ids.shape[1]

    t0 = time.time()
    cache = DynamicCache()

    # PREFILL
    hidden = s0_embed(input_ids)
    position_ids = torch.arange(seq_len, device=hidden.device).unsqueeze(0)
    position_embeddings = s0_rotary(hidden, position_ids)

    hidden = run_stage_prefill(s0_layers, hidden, position_ids, position_embeddings, cache, 0)

    xfer = hidden.nelement() * hidden.element_size() / (1024*1024)
    print(f"  [传输-Prefill] Stage 0 -> Stage 1: {xfer:.2f} MB")

    hidden = run_stage_prefill(s1_layers, hidden, position_ids, position_embeddings, cache, half)
    hidden = s1_norm(hidden)

    logits = s1_lm(hidden[:, -1:, :])
    first_token = torch.argmax(logits[:, -1, :], dim=-1)
    generated = []
    if first_token.item() != tokenizer.eos_token_id:
        generated.append(first_token.item())

    # DECODE
    cur_pos = seq_len
    hidden_dim = model.config.hidden_size

    for t in range(max_tokens - 1):
        if not generated or len(generated) >= max_tokens:
            break

        new_token_id = generated[-1]
        new_embed = s0_embed(torch.tensor([[new_token_id]], device=hidden.device)).to(model.dtype)
        new_pos = torch.tensor([[cur_pos]], device=hidden.device)
        dummy = torch.zeros(1, 1, hidden_dim, device=hidden.device, dtype=model.dtype)
        new_pe = s0_rotary(dummy, new_pos)

        s0_out = run_stage_decode_one_token(s0_layers, new_embed, new_pos, new_pe, cache, 0)

        s1_out = run_stage_decode_one_token(s1_layers, s0_out, new_pos, new_pe, cache, half)
        s1_out = s1_norm(s1_out)

        logits = s1_lm(s1_out)
        next_token = torch.argmax(logits[:, -1, :], dim=-1)
        if next_token.item() == tokenizer.eos_token_id:
            break
        generated.append(next_token.item())
        cur_pos += 1

    elapsed = time.time() - t0
    resp = tokenizer.decode(generated, skip_special_tokens=True)
    print(f"  Token: {len(generated)}, 耗时: {elapsed:.3f}s, 回复: {resp}")

    del s0_layers, s1_layers, s1_norm, s1_lm
    gc.collect()
    return resp, elapsed


def main():
    print_sep("Pipeline 切片实验 v3 - DynamicCache")
    print(f"  模型: {MODEL_NAME}")
    print(f"  输入: \"{PROMPT}\"")

    print_sep("加载模型")
    config = AutoConfig.from_pretrained(MODEL_NAME, trust_remote_code=True)
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME, trust_remote_code=True, low_cpu_mem_usage=True
    )
    print(f"  模型 dtype: {model.dtype}")
    model.eval()
    print(f"  参数: {sum(p.numel() for p in model.parameters())/1e6:.1f}M, 层: {config.num_hidden_layers}")

    # 实验 1
    print_sep("实验 1: 完整模型 (基准)")
    full_resp, full_time = full_inference(model, tokenizer, PROMPT)

    # 实验 2
    print_sep("实验 2: Pipeline 2阶段 + KV Cache")
    pipe_resp, pipe_time = pipeline_kv(model, tokenizer, PROMPT, num_stages=2, label="Pipeline 2阶段")

    # 实验 3
    print_sep("实验 3: 双分片独立模型 + KV Cache")
    split_resp, split_time = split_model_pipeline_kv(model, tokenizer, PROMPT)

    # 对比
    print_sep("结果对比")
    print(f"  完整模型:       \"{full_resp}\" ({full_time:.3f}s)")
    print(f"  Pipeline(KV):   \"{pipe_resp}\" ({pipe_time:.3f}s)")
    print(f"  双分片独立(KV): \"{split_resp}\" ({split_time:.3f}s)")

    m1 = full_resp.strip() == pipe_resp.strip()
    m2 = full_resp.strip() == split_resp.strip()
    m3 = pipe_resp.strip() == split_resp.strip()

    print(f"\n  ✅ 完整 vs Pipeline:   {'PASS' if m1 else 'FAIL'}")
    print(f"  ✅ 完整 vs 双分片:     {'PASS' if m2 else 'FAIL'}")
    print(f"  ✅ Pipeline vs 双分片: {'PASS' if m3 else 'FAIL'}")

    all_pass = m1 and m2 and m3
    if all_pass:
        print(f"\n  🎉🎉🎉 三组实验结果完全一致！Pipeline 切片验证通过！")
    else:
        print(f"\n  ⚠️ 结果不一致，需要进一步调试")

    output = {
        "model": MODEL_NAME, "prompt": PROMPT,
        "total_layers": config.num_hidden_layers,
        "results": {
            "full": {"response": full_resp, "time": round(full_time, 3)},
            "pipeline": {"response": pipe_resp, "time": round(pipe_time, 3)},
            "split": {"response": split_resp, "time": round(split_time, 3)},
        },
        "all_consistent": all_pass,
        "consistency": {"full_vs_pipeline": m1, "full_vs_split": m2, "pipeline_vs_split": m3}
    }
    out_path = "/home/z/my-project/download/pipeline_test_results.json"
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"  结果已保存: {out_path}")

    return all_pass


if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
