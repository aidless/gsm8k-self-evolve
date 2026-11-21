"""Remote-side receipt computation for the cloud DPO adapter.

No GPU, no training — reads the artifact bytes that the cloud trainer wrote and
emits the same receipt shape as evokit.adapter_receipt.AdapterArtifactUpdater.
Run on the cloud host where the adapter lives; the small JSON is pulled back.
"""
import hashlib
import json
import struct
import sys
from pathlib import Path

root = Path(sys.argv[1])
weights = root / "adapter_model.safetensors"
config = root / "adapter_config.json"
states = sorted(root.glob("checkpoint-*/trainer_state.json"))
if not states and (root / "trainer_state.json").is_file():
    states = [root / "trainer_state.json"]
if not weights.is_file():
    print(json.dumps({"error": "missing: adapter_model.safetensors"}))
    sys.exit(2)
if not states:
    print(json.dumps({"error": "steps_unknown: no trainer_state.json"}))
    sys.exit(3)

# sha256 of full bytes
sha = hashlib.sha256()
with weights.open("rb") as fh:
    for chunk in iter(lambda: fh.read(1 << 20), b""):
        sha.update(chunk)
adapter_sha = sha.hexdigest()

# safetensors header + lora_B nonzero check
with weights.open("rb") as fh:
    n = struct.unpack("<Q", fh.read(8))[0]
    header = json.loads(fh.read(n))
base = 8 + n
lora_b = [k for k in header if k != "__metadata__" and "lora_B" in k]
all_zero = True
for name in lora_b:
    start, end = header[name]["data_offsets"]
    with weights.open("rb") as fh:
        fh.seek(base + start)
        chunk = fh.read(end - start)
    if any(b != 0 for b in chunk):
        all_zero = False
        break

state = json.loads(states[-1].read_text())
steps = int(state["global_step"])
cfg = json.loads(config.read_text())

receipt = {
    "adapter_sha256": adapter_sha,
    "verifier_id": "verifier-frozen-v1",
    "steps": steps,
    "steps_source": str(states[-1].relative_to(root)),
    "adapter_path": str(root),
    "base_model": cfg.get("base_model_name_or_path"),
    "lora_r": cfg.get("r"),
    "lora_alpha": cfg.get("lora_alpha"),
    "lora_b_nonzero": (not all_zero),
    "lora_b_tensors": len(lora_b),
    "bytes": weights.stat().st_size,
}
print(json.dumps(receipt, ensure_ascii=False, indent=2))
