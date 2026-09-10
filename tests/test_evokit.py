# tests/test_evokit.py
import math
from evokit.stats import mcnemar_two_sided

def test_mcnemar_round2_values():
    assert abs(mcnemar_two_sided(33, 4) - 1.0843941709026694e-06) < 1e-20

def test_mcnemar_empty():
    assert mcnemar_two_sided(0, 0) == 1.0

def test_registry_transition(tmp_path):
    import json
    from evokit.registry import VersionRegistry
    reg_path = tmp_path / "r.json"
    reg_path.write_text(json.dumps({"versions": {"v1": {"level": "provisional"}}}))
    reg = VersionRegistry(reg_path)
    evt = reg.transition("v1", "stable", {"statistical_passed": True}, reason="t")
    assert json.loads(reg_path.read_text())["versions"]["v1"]["level"] == "stable"
    assert evt["to"] == "stable"

def test_sign_roundtrip():
    from evokit.signing import generate_keypair, sign_bundle, verify_envelope
    priv, pub = generate_keypair()
    bundle = {"bundle_id": "x@abc", "sha256": "0" * 64, "manifest": {}}
    env = sign_bundle(bundle, priv, "agent-self", "2027-09-10T00:00:00+00:00")
    assert verify_envelope(env, bundle, {"agent-self": pub})["valid"] is True
