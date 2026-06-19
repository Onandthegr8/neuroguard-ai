"""Role-Based Access Control decorators and dependency helpers."""

from enum import StrEnum
from functools import wraps
from typing import Callable

from fastapi import Depends, HTTPException, status

from .jwt import get_current_user


class Role(StrEnum):
    USER = "user"
    CLINICIAN = "clinician"
    HOSPITAL_ADMIN = "hospital_admin"
    SUPER_ADMIN = "super_admin"


_ROLE_HIERARCHY = {
    Role.USER: 0,
    Role.CLINICIAN: 1,
    Role.HOSPITAL_ADMIN: 2,
    Role.SUPER_ADMIN: 3,
}


def require_role(*roles: Role) -> Callable:
    """FastAPI dependency — raises 403 if the JWT role is not in the allowed set."""

    async def _check(current_user: dict = Depends(get_current_user)) -> dict:
        user_role = current_user.get("role", Role.USER)
        if user_role not in roles and user_role != Role.SUPER_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{user_role}' is not authorized for this endpoint. Required: {[r.value for r in roles]}",
            )
        return current_user

    return _check


def require_min_role(min_role: Role) -> Callable:
    """Allow any role with hierarchy level >= min_role."""

    async def _check(current_user: dict = Depends(get_current_user)) -> dict:
        user_role = current_user.get("role", Role.USER)
        if _ROLE_HIERARCHY.get(user_role, 0) < _ROLE_HIERARCHY[min_role]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient privileges. Minimum required: {min_role}",
            )
        return current_user

    return _check


def require_owner_or_role(*roles: Role) -> Callable:
    """Allow if caller is the resource owner OR has one of the specified roles."""

    async def _check(user_id: str, current_user: dict = Depends(get_current_user)) -> dict:
        caller_id = str(current_user.get("sub", ""))
        caller_role = current_user.get("role", Role.USER)
        if caller_id == user_id or caller_role in roles or caller_role == Role.SUPER_ADMIN:
            return current_user
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    return _check
