from __future__ import annotations

import base64
import hashlib

import yaml
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat


def verify_signature(spec_raw: str, public_key_b64: str, signature_b64: str) -> bool:
    """Verify an Ed25519 signature over the canonical YAML of a contract spec.

    The message signed is SHA256(canonical_yaml) where canonical_yaml is the
    spec YAML with the provenance block stripped and keys sorted — identical
    to what the CLI's `covenant sign` produces.

    Args:
        spec_raw: Raw YAML text of the spec.
        public_key_b64: Base64-encoded Ed25519 public key (32 bytes).
        signature_b64: Base64-encoded signature (64 bytes).

    Returns:
        True if the signature is valid, False otherwise.
    """
    try:
        raw_dict = yaml.safe_load(spec_raw)
        if not isinstance(raw_dict, dict):
            return False

        # Strip provenance block (same as CLI sign command)
        canonical_dict = {k: v for k, v in raw_dict.items() if k != "provenance"}
        canonical_yaml = yaml.dump(canonical_dict, sort_keys=True).encode()
        message = hashlib.sha256(canonical_yaml).digest()

        pub_key_bytes = base64.b64decode(public_key_b64)
        sig_bytes = base64.b64decode(signature_b64)

        pub_key = Ed25519PublicKey.from_public_bytes(pub_key_bytes)
        pub_key.verify(sig_bytes, message)
        return True
    except (InvalidSignature, Exception):
        return False
