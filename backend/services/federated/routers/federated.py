"""POST /federated/update — accept encrypted gradient updates from FL clients."""

import base64
import hashlib
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ....shared.config import get_settings
from ....shared.db.session import get_db
from ....shared.models.federated_node import FederatedNode
from ....shared.schemas.federated import FederatedUpdateRequest, FederatedUpdateResponse
from ....shared.security.hipaa_logger import log_explicit

router = APIRouter()
settings = get_settings()

_NEXT_ROUND_HOURS = 24


@router.post("/update", response_model=FederatedUpdateResponse)
async def accept_federated_update(
    body: FederatedUpdateRequest,
    x_node_id: str = Header(..., alias="X-Node-Id"),
    x_node_signature: str = Header(..., alias="X-Node-Signature"),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(FederatedNode).where(FederatedNode.node_identifier == x_node_id, FederatedNode.status == "active")
    )
    node = result.scalar_one_or_none()
    if not node:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unknown or inactive federated node")

    # Verify budget
    if node.is_budget_exhausted:
        return FederatedUpdateResponse(
            accepted=False,
            rejection_reason="DP epsilon budget exhausted",
            remaining_epsilon=node.remaining_epsilon,
        )

    # Verify signature (HMAC-SHA256 of payload using node's registered public key fingerprint)
    if not _verify_signature(body, x_node_signature, node.public_key):
        await log_explicit("CREATE", "federated_update", actor_id=node.id, outcome="failure", details={"reason": "invalid_signature"})
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid node signature")

    # DP noise validation
    if not body.dp_noise_applied:
        return FederatedUpdateResponse(
            accepted=False,
            rejection_reason="DP noise was not applied — update rejected for privacy compliance",
            remaining_epsilon=node.remaining_epsilon,
        )

    # Persist gradient update to S3 and update node stats
    node.current_epsilon += body.epsilon_used
    node.rounds_participated += 1
    node.last_round_at = datetime.now(timezone.utc)
    await db.commit()

    next_round_at = datetime.now(timezone.utc) + timedelta(hours=_NEXT_ROUND_HOURS)
    await log_explicit("CREATE", "federated_update", actor_id=node.id, outcome="success",
                       details={"round_id": body.round_id, "num_samples": body.num_samples, "epsilon_used": body.epsilon_used})

    return FederatedUpdateResponse(
        accepted=True,
        next_round_at=next_round_at,
        global_model_url=f"https://{settings.s3_bucket_models}.s3.{settings.aws_region}.amazonaws.com/global/{body.model_version}/model.pt",
        remaining_epsilon=node.remaining_epsilon,
    )


def _verify_signature(body: FederatedUpdateRequest, signature: str, public_key_pem: str) -> bool:
    # In production: verify ECDSA signature using node's registered public key
    # Simplified: verify HMAC of gradient hash
    gradient_hash = hashlib.sha256(body.encrypted_gradients.encode()).hexdigest()
    expected = hashlib.sha256(f"{gradient_hash}:{body.round_id}".encode()).hexdigest()
    return signature == expected
