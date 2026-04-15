from __future__ import annotations

import base64
import hashlib

import pytest
import yaml
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from httpx import AsyncClient


def _sign_spec(spec_raw: str) -> tuple[str, str]:
    """Sign a spec and return (public_key_b64, signature_b64)."""
    raw_dict = yaml.safe_load(spec_raw)
    canonical_dict = {k: v for k, v in raw_dict.items() if k != "provenance"}
    canonical_yaml = yaml.dump(canonical_dict, sort_keys=True).encode()
    message = hashlib.sha256(canonical_yaml).digest()

    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    sig = private_key.sign(message)
    pub_bytes = public_key.public_bytes_raw()

    return base64.b64encode(pub_bytes).decode(), base64.b64encode(sig).decode()


SPEC_RAW = """\
covenant: "1.0"
agent:
  name: signed-agent
  version: 1.0.0
  runtime: python
capabilities:
  tools:
    - read_file
constraints:
  budget:
    max_cost_usd: 1.0
"""


async def test_verify_valid_signature(client: AsyncClient):
    pub_key, signature = _sign_spec(SPEC_RAW)
    resp = await client.post(
        "/verify",
        json={"spec_raw": SPEC_RAW, "public_key": pub_key, "signature": signature},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["valid"] is True
    assert "valid" in data["message"].lower()


async def test_verify_tampered_spec_fails(client: AsyncClient):
    pub_key, signature = _sign_spec(SPEC_RAW)
    tampered = SPEC_RAW.replace("read_file", "bash")
    resp = await client.post(
        "/verify",
        json={"spec_raw": tampered, "public_key": pub_key, "signature": signature},
    )
    assert resp.status_code == 200
    assert resp.json()["valid"] is False


async def test_verify_wrong_key_fails(client: AsyncClient):
    _, signature = _sign_spec(SPEC_RAW)
    # Generate a different key pair for the wrong public key
    wrong_priv = Ed25519PrivateKey.generate()
    wrong_pub = base64.b64encode(
        wrong_priv.public_key().public_bytes_raw()
    ).decode()
    resp = await client.post(
        "/verify",
        json={"spec_raw": SPEC_RAW, "public_key": wrong_pub, "signature": signature},
    )
    assert resp.status_code == 200
    assert resp.json()["valid"] is False


async def test_verify_invalid_base64_returns_false(client: AsyncClient):
    resp = await client.post(
        "/verify",
        json={
            "spec_raw": SPEC_RAW,
            "public_key": "not-valid-base64!!!",
            "signature": "also-not-valid!!!",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["valid"] is False
