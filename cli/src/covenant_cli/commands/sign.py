from __future__ import annotations

import base64
import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path

import typer
import yaml

from covenant_cli import output
from covenant_cli.errors import EXIT_SIGNING, EXIT_VALIDATION, SpecLoadError
from covenant_cli.models import spec_loader
from covenant_cli.services import linter


def sign_cmd(
    path: Path = typer.Argument(..., help="Path to .covenant.yaml"),
) -> None:
    """Sign a .covenant.yaml with an Ed25519 key, writing provenance block.

    The provenance block is always appended at the end of the file.
    COVENANT_SIGNING_KEY must be a base64url-encoded Ed25519 private key.
    """
    try:
        spec = spec_loader.load_spec(path)
    except SpecLoadError as e:
        output.error_panel(f"[{e.phase.upper()}] {'; '.join(e.issues)}")
        raise typer.Exit(e.exit_code)

    # Lint -- block on errors, warn is ok
    issues = linter.lint(spec)
    error_issues = [i for i in issues if i.level == "error"]
    if issues:
        output.issues_table(issues)
    if error_issues:
        output.error_panel("Spec has lint errors -- fix them before signing.")
        raise typer.Exit(EXIT_VALIDATION)

    signing_key_b64 = os.environ.get("COVENANT_SIGNING_KEY")
    if not signing_key_b64:
        output.error_panel(
            "COVENANT_SIGNING_KEY is not set.",
            hint="Export a base64url-encoded Ed25519 private key.",
        )
        raise typer.Exit(EXIT_SIGNING)

    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

        priv_bytes = base64.urlsafe_b64decode(signing_key_b64)
        private_key = Ed25519PrivateKey.from_private_bytes(priv_bytes)
        public_key = private_key.public_key()
        pub_b64 = base64.urlsafe_b64encode(public_key.public_bytes_raw()).decode()
    except Exception as e:
        output.error_panel(f"Failed to load signing key: {e}")
        raise typer.Exit(EXIT_SIGNING)

    try:
        raw_dict = yaml.safe_load(path.read_text(encoding="utf-8"))

        # Strip existing provenance -- must not be included in signed content
        raw_no_prov = {k: v for k, v in raw_dict.items() if k != "provenance"}

        # Canonical YAML: keys sorted recursively, no comments
        canonical = yaml.dump(raw_no_prov, sort_keys=True, allow_unicode=True).encode()
        digest = hashlib.sha256(canonical).digest()

        sig_bytes = private_key.sign(digest)
        sig_b64 = base64.urlsafe_b64encode(sig_bytes).decode()

        raw_dict["provenance"] = {
            "algorithm": "Ed25519",
            "public_key": pub_b64,
            "signature": sig_b64,
            "signed_at": datetime.now(tz=timezone.utc).isoformat(),
        }

        path.write_text(
            yaml.dump(raw_dict, sort_keys=False, allow_unicode=True), encoding="utf-8"
        )

    except Exception as e:
        output.error_panel(f"Signing failed: {e}")
        raise typer.Exit(EXIT_SIGNING)

    fingerprint = pub_b64[:16]
    output.success_panel(
        f"Signed  {spec.agent.name} {spec.agent.version}",
        body_lines=[
            f"Key fingerprint: {fingerprint}...",
            f"Provenance written to {path.absolute()}",
        ],
    )
