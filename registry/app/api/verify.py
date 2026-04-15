from __future__ import annotations

from fastapi import APIRouter

from app.models.schemas import VerifyRequest, VerifyResponse
from app.services.verify import verify_signature

router = APIRouter(tags=["verify"])


@router.post("/verify", response_model=VerifyResponse)
async def verify_contract_signature(body: VerifyRequest) -> VerifyResponse:
    """Verify an Ed25519 signature over a contract spec.

    Returns valid=True if the signature matches the public key over
    SHA256(canonical YAML with provenance stripped).
    """
    valid = verify_signature(body.spec_raw, body.public_key, body.signature)
    return VerifyResponse(
        valid=valid,
        message="Signature is valid." if valid else "Signature verification failed.",
    )
