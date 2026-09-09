"""Independent re-verification of the step-calc stable-promotion evidence chain.

Recomputes everything from the files in this repo (no trust in cached claims):
  1. bundle.sha256 == sha256(canonical-JSON(manifest))
  2. all 5 manifest artifact hashes match the repo files
  3. merged held-out 200-question paired exact McNemar recomputed from the
     per-question results (batch1) + authoritative paired counts (batch2),
     ledger identity (step-concise == better-worse) asserted, values matched
     against manifest.heldout_evidence
  4. train / held1 / held2 question-id sets pairwise disjoint, matched
     against manifest.disjoint_check
  5. Ed25519 envelope verification, replicating the signer's exact semantics:
     envelope.bundle_id/sha256 must equal bundle's; signer must be the
     trusted key in signed/agent-self.pub.hex; signature must be valid over
     canonical_payload(bundle_id, bundle_sha256, signer, signed_at,
     expires_at) = json.dumps(..., sort_keys=True, separators=(",",":"));
     signature must not be expired.

Needs only stdlib + `cryptography` (pip install -r requirements.txt).
Exit 0 iff every check passes; otherwise prints the failing check and exits 1.

Manifest file keys are the original cloud paths (/root/exp-gsm8k/...);
they are resolved to repo files by basename.
"""
import base64
import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

BASENAME_MAP = {
    "active.json": REPO / "active.json",
    "gsm8k_evaluator.py": REPO / "examples" / "gsm8k_evaluator.py",
    "gsm8k40.json": REPO / "examples" / "gsm8k40.json",
    "heldout40.json": REPO / "examples" / "heldout40.json",
    "heldout-batch2-160.json": REPO / "examples" / "heldout-batch2-160.json",
}

PASS_COUNT = 200


def fail(msg):
    print(f"FAIL: {msg}")
    sys.exit(1)


def canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()


def binom_tail_two_sided(better, worse):
    n = better + worse
    if n == 0:
        return 1.0
    k = min(better, worse)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / (2 ** n)
    return min(1.0, 2 * tail)


def main() -> None:
    bundle = json.loads((REPO / "signed" / "bundle.json").read_text(encoding="utf-8"))
    envelope = json.loads(
        (REPO / "signed" / "step-calc@ad35903f5cb4.envelope.json").read_text(encoding="utf-8")
    )
    manifest = bundle["manifest"]

    # ---- 1. bundle digest binds the manifest ----
    digest = hashlib.sha256(canonical(manifest)).hexdigest()
    if digest != bundle["sha256"]:
        fail(f"bundle digest mismatch: recomputed {digest} != recorded {bundle['sha256']}")
    print(f"PASS [1/5] bundle.sha256 == sha256(canonical manifest) = {digest[:12]}...")

    # ---- 2. artifact file hashes ----
    files = manifest["files"]
    if set(BASENAME_MAP) != {Path(k).name for k in files}:
        fail(f"manifest file set changed: {sorted(files)}")
    for cloud_path, recorded in files.items():
        local = BASENAME_MAP[Path(cloud_path).name]
        recomputed = hashlib.sha256(local.read_bytes()).hexdigest()
        if recomputed != recorded:
            fail(f"artifact hash mismatch for {local.name}")
    print("PASS [2/5] all 5 manifest artifact sha256 match repo files")

    # ---- 3. merged held-out McNemar, recomputed ----
    b1 = json.loads((REPO / "results" / "heldout-round2-result.json").read_text(encoding="utf-8"))
    b2 = json.loads((REPO / "results" / "heldout-batch2-result.json").read_text(encoding="utf-8"))
    a1 = {x["id"]: x["passed"] for x in b1["concise_reason"]["details"]}
    s1 = {x["id"]: x["passed"] for x in b1["step_calc"]["details"]}
    if set(a1) != set(s1):
        fail("batch1 per-question id sets differ between policies")
    bt1 = sum(1 for i in a1 if (not a1[i]) and s1[i])
    ws1 = sum(1 for i in a1 if a1[i] and (not s1[i]))
    bt2, ws2 = b2["paired"]["step_better"], b2["paired"]["concise_better"]
    better, worse = bt1 + bt2, ws1 + ws2
    concise_total = b1["concise_reason"]["passed"] + b2["concise_reason"]["passed"]
    step_total = b1["step_calc"]["passed"] + b2["step_calc"]["passed"]
    if (step_total - concise_total) != (better - worse):
        fail("ledger identity violated: (step-concise) != (better-worse)")
    p = binom_tail_two_sided(better, worse)
    ev = manifest["heldout_evidence"]
    checks = {
        "n": PASS_COUNT,
        "concise_reason_passed": concise_total,
        "step_calc_passed": step_total,
        "paired_better": better,
        "paired_worse": worse,
    }
    for k, v in checks.items():
        if ev[k] != v:
            fail(f"heldout_evidence[{k}]: recomputed {v} != recorded {ev[k]}")
    if abs(ev["mcnemar_p_value"] - p) > 1e-15:
        fail(f"mcnemar p mismatch: recomputed {p} != recorded {ev['mcnemar_p_value']}")
    print(f"PASS [3/5] merged held-out 200: concise {concise_total} vs step {step_total}, "
          f"better:worse = {better}:{worse}, exact McNemar p = {p:.4e}")

    # ---- 4. question sets pairwise disjoint ----
    def ids_of(path):
        return {c["id"] for c in json.loads(Path(path).read_text(encoding="utf-8"))["cases"]}

    train = ids_of(REPO / "examples" / "gsm8k40.json")
    h1 = ids_of(REPO / "examples" / "heldout40.json")
    h2 = ids_of(REPO / "examples" / "heldout-batch2-160.json")
    if (train & h1) or (train & h2) or (h1 & h2):
        fail("question-id overlap detected between train/held1/held2")
    dj = manifest["disjoint_check"]
    if (dj["train_n"], dj["held1_n"], dj["held2_n"]) != (len(train), len(h1), len(h2)):
        fail("disjoint_check counts do not match recomputed set sizes")
    print(f"PASS [4/5] sets disjoint: train={len(train)}, held1={len(h1)}, held2={len(h2)}")

    # ---- 5. Ed25519 envelope (signer-exact semantics) ----
    if envelope.get("algorithm") != "Ed25519":
        fail("unsupported algorithm")
    if envelope.get("bundle_id") != bundle.get("bundle_id") or \
            envelope.get("bundle_sha256") != bundle.get("sha256"):
        fail("envelope does not bind this bundle")
    pub = bytes.fromhex((REPO / "signed" / "agent-self.pub.hex").read_text().strip())
    if envelope.get("signer") != "agent-self":
        fail("untrusted signer")
    exp = datetime.fromisoformat(envelope["expires_at"])
    exp = exp if exp.tzinfo else exp.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) > exp:
        fail("signature expired")
    payload = canonical({
        "bundle_id": envelope["bundle_id"],
        "bundle_sha256": envelope["bundle_sha256"],
        "signer": envelope["signer"],
        "signed_at": envelope["signed_at"],
        "expires_at": envelope["expires_at"],
    })
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        Ed25519PublicKey.from_public_bytes(pub).verify(
            base64.b64decode(envelope["signature"]), payload)
    except Exception as exc:
        fail(f"Ed25519 verify failed: {type(exc).__name__}")
    print(f"PASS [5/5] Ed25519 self-signature valid (signer=agent-self, "
          f"expires {envelope['expires_at'][:10]})")

    print(f"\nALL CHECKS PASSED: {bundle['bundle_id']} "
          f"(step-calc stable, held-out 200, p={p:.4e})")


if __name__ == "__main__":
    main()
