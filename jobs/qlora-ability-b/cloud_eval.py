"""云端评测驱动：加载 base(+SFT)[+DPO]，对 heldout 生成，落 JSON 供本地判分。

只负责生成，不判分（判分在本地 eval_ability 做，可复算）。两组用完全相同的解码参数
(do_sample=False, max_new_tokens=96)，唯一差别是是否叠 DPO adapter。

用法（云端，ROCm torch + transformers + peft 在 /opt/venv）：
  /opt/venv/bin/python cloud_eval.py --base /workspace/models/Qwen3-4B \
      --sft /workspace/qlora-job/sft/checkpoint-136 \
      --heldout /workspace/qlora-job/ability/synth_heldout.jsonl \
      --dpo /workspace/qlora-job/ability/out/adapter_model.safetensors \
      --out-dir /workspace/qlora-job/ability/eval

产物 eval/generations_sft.json 与 eval/generations_dpo.json（每题 {id, answer, text}）。
"""
import argparse
import json
import sys
from pathlib import Path


def load_model(base, sft, dpo=None, gpu_mem=None):
    """加载 base(+adapter)。dpo 与 sft **互斥**，不相叠加。

    口径：train_dpo.py 的 `resume_sft` 路径是 `PeftModel.from_pretrained(base, sft,
    is_trainable=True)` 后继续训练并 `save_pretrained(out_dir)` —— 输出的是**同一个**
    adapter，DPO 更新直接写在这份已含 SFT 的 LoRA 上。所以新 DPO adapter 已经带了
    SFT 贡献，再叠一份 SFT 就是重复加载同一份 LoRA 两次（口径错）。
    故：A 组 = base+sft；B 组 = base+dpo（dpo 自己就含 SFT）。
    """
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    tok = AutoTokenizer.from_pretrained(base, trust_remote_code=True)
    if tok.pad_token_id is None:
        tok.pad_token = tok.eos_token
    kw = dict(dtype=torch.bfloat16, trust_remote_code=True)
    if gpu_mem:
        kw["attn_implementation"] = "sdpa"
    model = AutoModelForCausalLM.from_pretrained(base, **kw)
    # 必须显式搬到 GPU：from_pretrained 默认留在 CPU，generate 会退化成
    # CPU 上位逐 token 解码（实测 4B bf16 在 CPU 上 31 分钟出不来 60 题，
    # GPU use=0%/CPU 满载）。device_map 交给 accelerate 或 .to("cuda") 均可。
    if not getattr(model, "hf_device_map", None):
        model = model.to("cuda")
    adapter = dpo or sft
    if adapter:
        from peft import PeftModel
        model = PeftModel.from_pretrained(model, adapter, is_trainable=False)
    model.eval()
    return model, tok


def generate(model, tok, prompts, max_new_tokens=96):
    import torch
    outs = []
    for p in prompts:
        enc = tok(p, return_tensors="pt").to(model.device)
        with torch.no_grad():
            gen = model.generate(**enc, max_new_tokens=max_new_tokens,
                                 do_sample=False, pad_token_id=tok.eos_token_id)
        text = tok.decode(gen[0][enc["input_ids"].shape[1]:], skip_special_tokens=True)
        outs.append(text)
    return outs


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--sft", default=None)
    ap.add_argument("--heldout", required=True)
    ap.add_argument("--dpo", default=None, help="DPO adapter 目录/文件；给了就多跑一组")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--max-new-tokens", type=int, default=96)
    args = ap.parse_args(argv)

    rows = []
    with open(args.heldout, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    prompts = [r["prompt"] for r in rows]
    print(f"[eval] heldout {len(rows)} 题", flush=True)

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    model, tok = load_model(args.base, args.sft, None)
    sft_texts = generate(model, tok, prompts, args.max_new_tokens)
    sft_rows = [{"id": r["id"], "answer": r["answer"], "text": t}
                for r, t in zip(rows, sft_texts)]
    (out / "generations_sft.json").write_text(
        json.dumps(sft_rows, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[eval] SFT 组生成完成 -> generations_sft.json", flush=True)

    if args.dpo:
        # B 组只挂 DPO adapter（已被 train_dpo 训在 SFT 之上，见 load_model 注释）
        model2, tok2 = load_model(args.base, None, args.dpo)
        dpo_texts = generate(model2, tok2, prompts, args.max_new_tokens)
        dpo_rows = [{"id": r["id"], "answer": r["answer"], "text": t}
                    for r, t in zip(rows, dpo_texts)]
        (out / "generations_dpo.json").write_text(
            json.dumps(dpo_rows, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"[eval] DPO 组生成完成 -> generations_dpo.json", flush=True)

    print(f"[done] generations -> {out}", flush=True)


if __name__ == "__main__":
    sys.exit(main())