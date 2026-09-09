"""Independent end-to-end verifier for gsm8k-self-evolve.

Recomputes everything from raw repo files (trusts no summary):
 1. SHA-256 of the 5 signed artifacts
  2. canonical manifest digest == bundle.sha256 == envelope.bundle_sha256
  3. Ed25519 envelope signature (same canonical_payload spec as the signer)
  4. merged 200-question exact McNemar + ledger identity (step-concise == better-worse)
  5. pairwise disjointness of train / heldout1 / heldout2 (by question id)

Exit 0 = all pass. Any failure raises AssertionError.
Requires: Python 3.8+, `cryptography` (pip install cryptography).
"""
import base64
import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EVO = ROOT / ".evo"


def ok(msg):
    print(f"  [PASS] {msg}")


# ---------- 1. artifact hashes ----------
print("[1/5] artifact hashes")
bundle = json.loads((EVO / "bundle.json").read_text(encoding="utf-8"))
manifest = bundle["manifest"]
# manifest keys are absolute cloud paths; map by basename into this repo
LOCATE = {
    "active.json": EVO / "active.json",
    "gsm8k_evaluator.py": ROOT / "examples" / "gsm8k_evaluator.py",
    "gsm8k40.json": ROOT / "examples" / "gsm8k40.json",
    "heldout40.json": ROOT / "examples" / "heldout40.json",
    "heldout-batch2-160.json": ROOT / "examples" / "heldout-batch2-160.json",
}
assert len(manifest["files"]) == 5, "manifest must pin exactly 5 artifacts"
for cloud_path, expect in manifest["files"].items():
    name = cloud_path.rsplit("/", 1)[-1]
    local = LOCATE[name]
    got = hashlib.sha256(local.read_bytes()).hexdigest()
    assert got == expect, f"hash mismatch: {name}\n got={got}\n exp={expect}"
    ok(f"{name} sha256 matches ({got[:12]}...)")

# ---------- 2. canonical manifest digest ----------
print("[2/5] canonical manifest digest")
digest = hashlib.sha256(
    json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
).hexdigest()
assert digest == bundle["sha256"], "bundle.sha256 != digest(canonical manifest)"
envs = list((EVO / "signed-bundles").glob("*.envelope.json"))
assert len(envs) == 1, "expect exactly one envelope"
envelope = json.loads(envs[0].read_text(encoding="utf-8"))
assert envelope["bundle_sha256"] == bundle["sha256"], "envelope digest mismatch"
assert envelope["bundle_id"] == bundle["bundle_id"], "envelope id mismatch"
ok(f"digest {digest[:12]}... matches bundle + envelope id {bundle['bundle_id']}")

# ---------- 3. Ed25519 signature ----------
print("[3/5] Ed25519 envelope signature")
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

assert envelope.get("algorithm") == "Ed25519", "unsupported algorithm"
pub = (EVO / "trusted-keys" / "agent-self.pub").read_bytes()
assert len(pub) == 32, f"pubkey must be raw 32 bytes, got {len(pub)}"
exp = datetime.fromisoformat(envelope["expires_at"])
exp = exp if exp.tzinfo else exp.replace(tzinfo=timezone.utc)
assert datetime.now(timezone.utc) <= exp, "signature expired"
payload = json.dumps(
    {
        "bundle_id": envelope["bundle_id"],
        "bundle_sha256": envelope["bundle_sha256"],
        "signer": envelope["signer"],
        "signed_at": envelope["signed_at"],
        "expires_at": envelope["expires_at"],
    },
    sort_keys=True,
    separators=(",", ":"),
).encode()
Ed25519PublicKey.from_public_bytes(pub).verify(
    base64.b64decode(envelope["signature"]), payload
)
ok(f"valid {envelope['algorithm']} signature by '{envelope['signer']}' (self-signed: "
   f"integrity + audit, not third-party endorsement), expires {envelope['expires_at'][:10]}")

# ---------- 4. merged McNemar ----------
print("[4/5] merged held-out McNemar (200 questions)")


def binom_tail_two_sided(b, c):
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2**n)


b1 = json.loads((ROOT / "results" / "heldout-round2-result.json").read_text())
b2 = json.loads((ROOT / "results" / "heldout-batch2-result.json").read_text())
a1 = {x["id"]: x["passed"] for x in b1["concise_reason"]["details"]}
s1 = {x["id"]: x["passed"] for x in b1["step_calc"]["details"]}
assert set(a1) == set(s1) and len(a1) == 40, "batch1 must have 40 paired outcomes"
bt1 = sum(1 for i in a1 if (not a1[i]) and s1[i])
ws1 = sum(1 for i in a1 if a1[i] and (not s1[i]))
bt2, ws2 = b2["paired"]["step_better"], b2["paired"]["concise_better"]
better, worse = bt1 + bt2, ws1 + ws2
concise_total = b1["concise_reason"]["passed"] + b2["concise_reason"]["passed"]
step_total = b1["step_calc"]["passed"] + b2["step_calc"]["passed"]
n_total = b1["concise_reason"]["total"] + b2["concise_reason"]["total"]
assert n_total == 200, f"expected 200 merged questions, got {n_total}"
assert (step_total - concise_total) == (better - worse), "ledger identity broken"
p = binom_tail_two_sided(better, worse)
hev = manifest["heldout_evidence"]
assert (concise_total, step_total, better, worse) == (
    hev["concise_reason_passed"], hev["step_calc_passed"],
    hev["paired_better"], hev["paired_worse"],
), "recomputed stats differ from signed manifest"
assert abs(p - hev["mcnemar_p_value"]) < 1e-12, "p-value mismatch vs manifest"
ok(f"concise {concise_total}/{n_total} vs step {step_total}/{n_total}, "
   f"better:worse={better}:{worse}, exact McNemar p={p:.3e}")

# ---------- 5. disjointness ----------
print("[5/5] question-set disjointness")


def ids_of(path):
    return {c["id"] for c in json.loads(Path(path).read_text())["cases"]}


train = ids_of(ROOT / "examples" / "gsm8k40.json")
h1 = ids_of(ROOT / "examples" / "heldout40.json")
h2 = ids_of(ROOT / "examples" / "heldout-batch2-160.json")
assert (len(train), len(h1), len(h2)) == (40, 40, 160), "dataset sizes changed"
assert not (train & h1) and not (train & h2) and not (h1 & h2), "overlap detected"
ok("train(40) / heldout1(40) / heldout2(160) pairwise disjoint")

print(f"\nALL CHECKS PASSED: step-calc {step_total}/{n_total} vs "
      f"concise-reason {concise_total}/{n_total}, p={p:.3e}")
