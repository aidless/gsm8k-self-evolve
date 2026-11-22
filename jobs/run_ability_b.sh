#!/usr/bin/env bash
# Ability-B: train DPO on synth_train.jsonl, then eval base+SFT vs base+DPO on heldout.
# Shared GPU is contested -> require free>=36GiB stable across 3 samples before training.
set -u
LOG=/workspace/logs/ability-b.log
PY=/opt/venv/bin/python
JOB=/workspace/qlora-job/ability
free_gb() { $PY -c "import torch;print(round(torch.cuda.mem_get_info()[0]/2**30,1))" 2>/dev/null || echo 0; }

echo "[$(date -u +%FT%TZ)] ability-b start" >> "$LOG"

TRAIN_OK=0
for attempt in $(seq 1 60); do
  stable=0
  f0=$(free_gb)
  echo "[$(date -u +%FT%TZ)] train attempt=$attempt probe=$f0" >> "$LOG"
  for i in 1 2 3; do
    sleep 12
    f=$(free_gb)
    pass=$(/bin/python3 -c "print(1 if float('$f')>=36 else 0)")
    if [ "$pass" = "1" ]; then stable=$((stable+1)); else stable=0; fi
    echo "[$(date -u +%FT%TZ)]   sample$i free=$f stable=$stable" >> "$LOG"
  done
  if [ $stable -ge 3 ]; then
    rm -rf "$JOB/out" && mkdir -p "$JOB/out"
    cd /workspace/qlora-job
    DPO_BASE_MODEL=/workspace/models/Qwen3-4B PYTORCH_ALLOC_CONF=expandable_segments:True \
      $PY train/train_dpo.py --p2 --no-4bit --gpu-mem-mib 12000 \
      --train-file "$JOB/synth_train.jsonl" \
      --sft-adapter /workspace/qlora-job/sft/checkpoint-136 \
      --out-dir "$JOB/out" \
      > /workspace/logs/ability-train.stdout 2> /workspace/logs/ability-train.stderr
    rc=$?
    echo "[$(date -u +%FT%TZ)] train attempt=$attempt rc=$rc" >> "$LOG"
    if [ $rc -eq 0 ] && [ -f "$JOB/out/adapter_model.safetensors" ]; then
      echo TRAIN_SUCCESS >> "$LOG"
      TRAIN_OK=1
      break
    fi
  fi
  sleep 45
done

if [ $TRAIN_OK -ne 1 ]; then
  echo TRAIN_FAILED >> "$LOG"
  exit 1
fi

EVAL_OK=0
for attempt in $(seq 1 40); do
  stable=0
  f0=$(free_gb)
  echo "[$(date -u +%FT%TZ)] eval attempt=$attempt probe=$f0" >> "$LOG"
  for i in 1 2 3; do
    sleep 10
    f=$(free_gb)
    pass=$(/bin/python3 -c "print(1 if float('$f')>=24 else 0)")
    if [ "$pass" = "1" ]; then stable=$((stable+1)); else stable=0; fi
    echo "[$(date -u +%FT%TZ)]   eval-sample$i free=$f stable=$stable" >> "$LOG"
  done
  if [ $stable -ge 3 ]; then
    rm -rf "$JOB/eval" && mkdir -p "$JOB/eval"
    PYTORCH_ALLOC_CONF=expandable_segments:True \
      $PY "$JOB/cloud_eval.py" \
      --base /workspace/models/Qwen3-4B \
      --sft /workspace/qlora-job/sft/checkpoint-136 \
      --dpo "$JOB/out" \
      --heldout "$JOB/synth_heldout.jsonl" \
      --out-dir "$JOB/eval" \
      > /workspace/logs/ability-eval.stdout 2> /workspace/logs/ability-eval.stderr
    rc=$?
    echo "[$(date -u +%FT%TZ)] eval attempt=$attempt rc=$rc" >> "$LOG"
    if [ $rc -eq 0 ] && [ -f "$JOB/eval/generations_dpo.json" ]; then
      echo EVAL_SUCCESS >> "$LOG"
      EVAL_OK=1
      break
    fi
  fi
  sleep 40
done

if [ $EVAL_OK -ne 1 ]; then
  echo EVAL_FAILED >> "$LOG"
  exit 2
fi

echo "[$(date -u +%FT%TZ)] ability-b done" >> "$LOG"
echo DONE
