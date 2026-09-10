import base64
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey, Ed25519PublicKey)
from datetime import datetime, timezone
import json

def _canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()

def generate_keypair():
    priv = Ed25519PrivateKey.generate()
    return (priv.private_bytes_raw(), priv.public_key().public_bytes_raw())

def sign_bundle(bundle, priv_raw: bytes, signer: str, expires_at: str) -> dict:
    priv = Ed25519PrivateKey.from_private_bytes(priv_raw)
    payload = {"bundle_id": bundle["bundle_id"], "bundle_sha256": bundle["sha256"],
               "signer": signer,
               "signed_at": datetime.now(timezone.utc).isoformat(),
               "expires_at": expires_at}
    sig = priv.sign(_canonical(payload))
    return {"payload": payload,
            "signature": base64.b64encode(sig).decode(),
            "signer_pub": base64.b64encode(
                priv.public_key().public_bytes_raw()).decode()}

def verify_envelope(envelope, bundle, trusted: dict) -> dict:
    p = envelope["payload"]
    if p["bundle_id"] != bundle["bundle_id"] or p["bundle_sha256"] != bundle["sha256"]:
        return {"valid": False, "reason": "bundle binding mismatch"}
    pub_raw = trusted.get(p["signer"])
    if pub_raw is None:
        return {"valid": False, "reason": "unknown signer"}
    try:
        Ed25519PublicKey.from_public_bytes(pub_raw).verify(
            base64.b64decode(envelope["signature"]), _canonical(p))
    except Exception as e:
        return {"valid": False, "reason": f"bad signature: {type(e).__name__}"}
    exp = datetime.fromisoformat(p["expires_at"])
    if exp <= datetime.now(timezone.utc):
        return {"valid": False, "reason": "expired"}
    return {"valid": True}
