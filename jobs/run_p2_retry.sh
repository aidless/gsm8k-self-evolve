#!/usr/bin/env bash
# p2 retry: shared GPU VRAM is contested by other tenants. Require free>=36GiB
# stable across 3 samples (12s apart) before launching, and cap gpu-mem-mib at
# 12000 to leave headroom for precompute's log_softmax buffer.
set -u
LOG=/workspace/logs/dpo-p2-retry.log
PY=/opt/venv/bin/python
free_gb() { $PY -c "import torch;print(round(torch.cuda.mem_get_info()[0]/2**30,1))" 2>/dev/null || echo 0; }
for attempt in $(seq 1 60); do
  stable=0
  f0=$(free_gb)
  echo "[$(date -u +%FT%TZ)] attempt=$attempt probe=$f0" >> "$LOG"
  for i in 1 2 3; do
    sleep 12
    f=$(free_gb)
    pass=$(/bin/python3 -c "print(1 if float('$f')>=36 else 0)")
    if [ "$pass" = "1" ]; then stable=$((stable+1)); else stable=0; fi
    echo "[$(date -u +%FT%TZ)]   sample$i free=$f stable=$stable" >> "$LOG"
  done
  if [ $stable -ge 3 ]; then
    cd /workspace/qlora-job
    rm -rf out/p2 && mkdir -p out/p2
    DPO_BASE_MODEL=/workspace/models/Qwen3-4B PYTORCH_ALLOC_CONF=expandable_segments:True \
      $PY train/train_dpo.py --p2 --no-4bit --gpu-mem-mib 12000 \
      --train-file /workspace/qlora-job/data/dpo_p0v2.jsonl \
      --sft-adapter /workspace/qlora-job/sft/checkpoint-136 \
      --out-dir /workspace/qlora-job/out/p2 \
      > /workspace/logs/dpo-p2.stdout 2> /workspace/logs/dpo-p2.stderr
    rc=$?
    echo "[$(date -u +%FT%TZ)] attempt=$attempt rc=$rc done" >> "$LOG"
    if [ $rc -eq 0 ] && [ -f /workspace/qlora-job/out/p2/adapter_model.safetensors ]; then
      echo P2_SUCCESS >> "$LOG"
      break
    fi
  fi
  sleep 45
done
