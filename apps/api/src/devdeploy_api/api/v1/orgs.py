"""Teams, memberships, notifications, audit log, API keys."""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from devdeploy_api.audit import write_audit
from devdeploy_api.deps import get_current_user, get_db
from devdeploy_api.models import (
    ApiKey,
    NotificationConfig,
    OrgAuditLog,
    OrganizationMember,
    User,
)
from devdeploy_api.project_service import ensure_personal_org, user_org_ids
from devdeploy_api.rbac import require_org_role
from devdeploy_api.schemas import (
    ApiKeyCreate,
    ApiKeyCreatedOut,
    ApiKeyOut,
    AuditLogOut,
    MemberInvite,
    MemberOut,
    MemberRoleUpdate,
    NotificationConfigIn,
    NotificationConfigOut,
)

router = APIRouter(prefix="/orgs", tags=["orgs"])


def _primary_org(db: DbSession, user: User):
    return ensure_personal_org(db, user)


@router.get("/me/members", response_model=list[MemberOut])
def list_my_org_members(
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[MemberOut]:
    org = _primary_org(db, user)
    rows = db.execute(
        select(OrganizationMember)
        .where(OrganizationMember.organization_id == org.id)
        .order_by(OrganizationMember.created_at.asc())
    ).scalars().all()
    out: list[MemberOut] = []
    for m in rows:
        u = db.get(User, m.user_id)
        out.append(
            MemberOut(
                id=m.id,
                user_id=m.user_id,
                email=u.email if u else None,
                display_name=u.display_name if u else None,
                role=m.role,
                created_at=m.created_at,
            )
        )
    return out


@router.post("/me/members", response_model=MemberOut, status_code=201)
def invite_member(
    body: MemberInvite,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> MemberOut:
    org = _primary_org(db, user)
    require_org_role(db, user, org.id, "admin")
    target = db.execute(
        select(User).where(User.email == str(body.email).lower())
    ).scalar_one_or_none()
    if target is None:
        # Create a placeholder user so invites work in local mock mode.
        target = User(email=str(body.email).lower(), display_name=str(body.email))
        db.add(target)
        db.flush()
    existing = db.execute(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == org.id,
            OrganizationMember.user_id == target.id,
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Already a member")
    membership = OrganizationMember(
        organization_id=org.id,
        user_id=target.id,
        role=body.role,
    )
    db.add(membership)
    write_audit(
        db,
        organization_id=org.id,
        actor=user,
        action="member.invite",
        resource_type="member",
        resource_id=str(target.id),
        detail=body.role,
    )
    db.commit()
    db.refresh(membership)
    return MemberOut(
        id=membership.id,
        user_id=target.id,
        email=target.email,
        display_name=target.display_name,
        role=membership.role,
        created_at=membership.created_at,
    )


@router.patch("/me/members/{member_id}", response_model=MemberOut)
def update_member_role(
    member_id: UUID,
    body: MemberRoleUpdate,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> MemberOut:
    org = _primary_org(db, user)
    require_org_role(db, user, org.id, "owner")
    membership = db.get(OrganizationMember, member_id)
    if membership is None or membership.organization_id != org.id:
        raise HTTPException(status_code=404, detail="Member not found")
    membership.role = body.role
    db.commit()
    db.refresh(membership)
    u = db.get(User, membership.user_id)
    return MemberOut(
        id=membership.id,
        user_id=membership.user_id,
        email=u.email if u else None,
        display_name=u.display_name if u else None,
        role=membership.role,
        created_at=membership.created_at,
    )


@router.get("/me/notifications", response_model=list[NotificationConfigOut])
def list_notifications(
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[NotificationConfigOut]:
    org = _primary_org(db, user)
    rows = db.execute(
        select(NotificationConfig).where(NotificationConfig.organization_id == org.id)
    ).scalars().all()
    return [NotificationConfigOut.model_validate(r) for r in rows]


@router.put("/me/notifications", response_model=NotificationConfigOut)
def upsert_notification(
    body: NotificationConfigIn,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> NotificationConfigOut:
    org = _primary_org(db, user)
    require_org_role(db, user, org.id, "admin")
    row = db.execute(
        select(NotificationConfig).where(
            NotificationConfig.organization_id == org.id,
            NotificationConfig.kind == body.kind,
        )
    ).scalar_one_or_none()
    if row is None:
        row = NotificationConfig(
            organization_id=org.id,
            kind=body.kind,
            enabled=body.enabled,
            target=body.target,
        )
        db.add(row)
    else:
        row.enabled = body.enabled
        row.target = body.target
    db.commit()
    db.refresh(row)
    return NotificationConfigOut.model_validate(row)


@router.get("/me/audit", response_model=list[AuditLogOut])
def list_audit(
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[AuditLogOut]:
    org = _primary_org(db, user)
    require_org_role(db, user, org.id, "viewer")
    rows = db.execute(
        select(OrgAuditLog)
        .where(OrgAuditLog.organization_id == org.id)
        .order_by(OrgAuditLog.created_at.desc())
        .limit(200)
    ).scalars().all()
    return [AuditLogOut.model_validate(r) for r in rows]


@router.get("/me/api-keys", response_model=list[ApiKeyOut])
def list_api_keys(
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ApiKeyOut]:
    org = _primary_org(db, user)
    require_org_role(db, user, org.id, "admin")
    rows = db.execute(
        select(ApiKey)
        .where(ApiKey.organization_id == org.id)
        .order_by(ApiKey.created_at.desc())
    ).scalars().all()
    return [ApiKeyOut.model_validate(r) for r in rows]


@router.post("/me/api-keys", response_model=ApiKeyCreatedOut, status_code=201)
def create_api_key(
    body: ApiKeyCreate,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ApiKeyCreatedOut:
    org = _primary_org(db, user)
    require_org_role(db, user, org.id, "admin")
    raw = f"dd_{secrets.token_urlsafe(32)}"
    token_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    row = ApiKey(
        organization_id=org.id,
        created_by_user_id=user.id,
        name=body.name.strip(),
        token_prefix=raw[:10],
        token_hash=token_hash,
    )
    db.add(row)
    write_audit(
        db,
        organization_id=org.id,
        actor=user,
        action="api_key.create",
        resource_type="api_key",
        resource_id=row.token_prefix,
    )
    db.commit()
    db.refresh(row)
    return ApiKeyCreatedOut(
        id=row.id,
        name=row.name,
        token=raw,
        token_prefix=row.token_prefix,
        created_at=row.created_at,
    )


@router.delete("/me/api-keys/{key_id}", status_code=204)
def revoke_api_key(
    key_id: UUID,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    org = _primary_org(db, user)
    require_org_role(db, user, org.id, "admin")
    row = db.get(ApiKey, key_id)
    if row is None or row.organization_id != org.id:
        raise HTTPException(status_code=404, detail="API key not found")
    row.revoked_at = datetime.now(UTC)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# Silence unused import if any
_ = user_org_ids
