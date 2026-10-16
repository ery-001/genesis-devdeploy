"""Org audit log helpers."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session as DbSession

from devdeploy_api.models import OrgAuditLog, User


def write_audit(
    db: DbSession,
    *,
    organization_id: uuid.UUID,
    actor: User | None,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    detail: str | None = None,
    commit: bool = False,
) -> OrgAuditLog:
    row = OrgAuditLog(
        organization_id=organization_id,
        actor_user_id=actor.id if actor else None,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        detail=detail,
    )
    db.add(row)
    if commit:
        db.commit()
        db.refresh(row)
    else:
        db.flush()
    return row
