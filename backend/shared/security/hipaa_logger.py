"""HIPAA §164.312(b) audit logging middleware.

Records every PHI access with actor, action, resource, outcome, and request metadata.
Logs are written to the append-only audit_logs table; the app DB role has no DELETE/UPDATE.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from ..db.session import AsyncSessionLocal
from ..models.audit_log import AuditLog

# Routes that touch PHI — anything else is exempt
_PHI_ROUTE_PREFIXES = (
    "/api/v1/health",
    "/api/v1/keystroke",
    "/api/v1/wearable",
    "/api/v1/risk",
    "/api/v1/reports",
    "/api/v1/patients",
    "/api/v1/clinician",
    "/api/v1/user",
    "/api/v1/federated",
)


class HIPAAAuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path
        is_phi = any(path.startswith(prefix) for prefix in _PHI_ROUTE_PREFIXES)

        response = await call_next(request)

        if is_phi:
            await _write_audit_log(request, response)

        return response


async def _write_audit_log(request: Request, response: Response) -> None:
    actor_id: Optional[uuid.UUID] = None
    actor_role: Optional[str] = None
    patient_id: Optional[uuid.UUID] = None

    if hasattr(request.state, "user"):
        u = request.state.user
        actor_id = u.get("sub")
        actor_role = u.get("role")

    if hasattr(request.state, "patient_id"):
        patient_id = request.state.patient_id

    action = _method_to_action(request.method)
    outcome = "success" if response.status_code < 400 else "failure"

    log = AuditLog(
        timestamp=datetime.now(timezone.utc),
        actor_id=actor_id,
        actor_role=actor_role,
        patient_id=patient_id,
        action=action,
        resource_type=_path_to_resource(request.url.path),
        resource_id=None,
        ip_address=_get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        outcome=outcome,
        details={"path": request.url.path, "status_code": response.status_code},
    )

    async with AsyncSessionLocal() as session:
        session.add(log)
        await session.commit()


def _method_to_action(method: str) -> str:
    return {"GET": "READ", "POST": "CREATE", "PUT": "UPDATE", "PATCH": "UPDATE", "DELETE": "DELETE"}.get(method, method)


def _path_to_resource(path: str) -> str:
    parts = [p for p in path.split("/") if p and not _is_uuid(p)]
    return parts[-1] if parts else "unknown"


def _is_uuid(s: str) -> bool:
    try:
        uuid.UUID(s)
        return True
    except ValueError:
        return False


def _get_client_ip(request: Request) -> Optional[str]:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


async def log_explicit(
    action: str,
    resource_type: str,
    resource_id: Optional[str] = None,
    actor_id: Optional[uuid.UUID] = None,
    actor_role: Optional[str] = None,
    patient_id: Optional[uuid.UUID] = None,
    outcome: str = "success",
    details: Optional[dict] = None,
) -> None:
    """Explicit audit log for non-HTTP events (consent, export, login)."""
    log = AuditLog(
        timestamp=datetime.now(timezone.utc),
        actor_id=actor_id,
        actor_role=actor_role,
        patient_id=patient_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        outcome=outcome,
        details=details or {},
    )
    async with AsyncSessionLocal() as session:
        session.add(log)
        await session.commit()
