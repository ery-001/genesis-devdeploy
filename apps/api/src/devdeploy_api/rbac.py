"""Organization role checks (owner > admin > developer > viewer)."""

from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from devdeploy_api.models import OrganizationMember, Project, User

ROLE_RANK = {
    "viewer": 1,
    "developer": 2,
    "admin": 3,
    "owner": 4,
}


def get_membership(
    db: DbSession, user: User, organization_id: uuid.UUID
) -> OrganizationMember | None:
    return db.execute(
        select(OrganizationMember)
        .where(OrganizationMember.organization_id == organization_id)
        .where(OrganizationMember.user_id == user.id)
    ).scalar_one_or_none()


def require_org_role(
    db: DbSession,
    user: User,
    organization_id: uuid.UUID,
    minimum: str,
) -> OrganizationMember:
    membership = get_membership(db, user, organization_id)
    if membership is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    need = ROLE_RANK.get(minimum, 99)
    have = ROLE_RANK.get(membership.role, 0)
    if have < need:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Requires {minimum} role (have {membership.role})",
        )
    return membership


def require_project_role(
    db: DbSession,
    user: User,
    project: Project,
    minimum: str,
) -> OrganizationMember:
    return require_org_role(db, user, project.organization_id, minimum)
