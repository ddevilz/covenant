import base64
import hashlib
import os
import shutil
from pathlib import Path

import yaml
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from typer.testing import CliRunner

from covenant_cli.main import app

runner = CliRunner()
FIXTURES = Path(__file__).parent / "fixtures"


def _make_key() -> tuple[str, str]:
    """Returns (private_key_b64url, public_key_b64url)."""
    priv = Ed25519PrivateKey.generate()
    pub = priv.public_key()
    return (
        base64.urlsafe_b64encode(priv.private_bytes_raw()).decode(),
        base64.urlsafe_b64encode(pub.public_bytes_raw()).decode(),
    )


def test_sign_round_trip(tmp_path: Path) -> None:
    priv_b64, _ = _make_key()
    dest = tmp_path / "signed.covenant.yaml"
    shutil.copy(FIXTURES / "unsigned.covenant.yaml", dest)

    result = runner.invoke(
        app, ["sign", str(dest)], env={"COVENANT_SIGNING_KEY": priv_b64}
    )
    assert result.exit_code == 0, result.output

    data = yaml.safe_load(dest.read_text())
    assert "provenance" in data
    assert data["provenance"]["algorithm"] == "Ed25519"
    assert "signature" in data["provenance"]
    assert "public_key" in data["provenance"]


def test_sign_verify_signature(tmp_path: Path) -> None:
    priv_b64, _ = _make_key()
    dest = tmp_path / "signed.covenant.yaml"
    shutil.copy(FIXTURES / "unsigned.covenant.yaml", dest)

    runner.invoke(app, ["sign", str(dest)], env={"COVENANT_SIGNING_KEY": priv_b64})

    data = yaml.safe_load(dest.read_text())
    sig = base64.urlsafe_b64decode(data["provenance"]["signature"])
    pub_key_bytes = base64.urlsafe_b64decode(data["provenance"]["public_key"])
    pub_key = Ed25519PublicKey.from_public_bytes(pub_key_bytes)

    # Reconstruct canonical: spec without provenance block, keys sorted
    data_no_prov = {k: v for k, v in data.items() if k != "provenance"}
    canonical = yaml.dump(data_no_prov, sort_keys=True, allow_unicode=True).encode()
    digest = hashlib.sha256(canonical).digest()

    # Should not raise ─ signature is valid
    pub_key.verify(sig, digest)


def test_sign_missing_key_env(tmp_path: Path) -> None:
    dest = tmp_path / "spec.yaml"
    shutil.copy(FIXTURES / "unsigned.covenant.yaml", dest)

    # Remove COVENANT_SIGNING_KEY from env
    env = {k: v for k, v in os.environ.items() if k != "COVENANT_SIGNING_KEY"}
    result = runner.invoke(app, ["sign", str(dest)], env=env)
    assert result.exit_code == 3


def test_sign_invalid_spec_aborts(tmp_path: Path) -> None:
    priv_b64, _ = _make_key()
    dest = tmp_path / "spec.yaml"
    shutil.copy(FIXTURES / "missing_budget.covenant.yaml", dest)

    result = runner.invoke(
        app, ["sign", str(dest)], env={"COVENANT_SIGNING_KEY": priv_b64}
    )
    assert result.exit_code == 1
