"""Project environment variables and secrets (encrypted at rest)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from devdeploy_api.audit import write_audit
from devdeploy_api.crypto_util import decrypt_secret, encrypt_secret
from devdeploy_api.deps import get_current_user, get_db
from devdeploy_api.models import ProjectVariable, User
from devdeploy_api.project_service import get_project_for_user
from devdeploy_api.rbac import require_project_role
from devdeploy_api.schemas import VariableCreate, VariableOut, VariableUpdate

router = APIRouter(prefix="/projects", tags=["variables"])


def _to_out(row: ProjectVariable) -> VariableOut:
    if row.is_secret:
        preview = "••••••••"
    else:
        try:
            val = decrypt_secret(row.value_encrypted)
            preview = val if len(val) <= 64 else val[:61] + "…"
        except ValueError:
            preview = "[undecryptable]"
    return VariableOut(
        id=row.id,
        project_id=row.project_id,
        key=row.key,
        is_secret=row.is_secret,
        environment_name=row.environment_name,
        value_preview=preview,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.get("/{project_id}/variables", response_model=list[VariableOut])
def list_variables(
    project_id: UUID,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[VariableOut]:
    get_project_for_user(db, user, project_id)
    rows = db.execute(
        select(ProjectVariable)
        .where(ProjectVariable.project_id == project_id)
        .order_by(ProjectVariable.key.asc())
    ).scalars().all()
    return [_to_out(r) for r in rows]


@router.post(
    "/{project_id}/variables",
    response_model=VariableOut,
    status_code=status.HTTP_201_CREATED,
)
def create_variable(
    project_id: UUID,
    body: VariableCreate,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> VariableOut:
    project = get_project_for_user(db, user, project_id)
    require_project_role(db, user, project, "developer")
    existing = db.execute(
        select(ProjectVariable).where(
            ProjectVariable.project_id == project_id,
            ProjectVariable.key == body.key,
            ProjectVariable.environment_name == body.environment_name,
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Variable already exists")
    row = ProjectVariable(
        project_id=project_id,
        key=body.key,
        value_encrypted=encrypt_secret(body.value),
        is_secret=body.is_secret,
        environment_name=body.environment_name,
    )
    db.add(row)
    write_audit(
        db,
        organization_id=project.organization_id,
        actor=user,
        action="variable.create",
        resource_type="variable",
        resource_id=body.key,
        detail=f"env={body.environment_name} secret={body.is_secret}",
    )
    db.commit()
    db.refresh(row)
    return _to_out(row)


@router.patch(
    "/{project_id}/variables/{variable_id}",
    response_model=VariableOut,
)
def update_variable(
    project_id: UUID,
    variable_id: UUID,
    body: VariableUpdate,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> VariableOut:
    project = get_project_for_user(db, user, project_id)
    require_project_role(db, user, project, "developer")
    row = db.get(ProjectVariable, variable_id)
    if row is None or row.project_id != project_id:
        raise HTTPException(status_code=404, detail="Variable not found")
    if body.value is not None:
        row.value_encrypted = encrypt_secret(body.value)
    if body.is_secret is not None:
        row.is_secret = body.is_secret
    write_audit(
        db,
        organization_id=project.organization_id,
        actor=user,
        action="variable.update",
        resource_type="variable",
        resource_id=row.key,
    )
    db.commit()
    db.refresh(row)
    return _to_out(row)


@router.delete(
    "/{project_id}/variables/{variable_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_variable(
    project_id: UUID,
    variable_id: UUID,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    project = get_project_for_user(db, user, project_id)
    require_project_role(db, user, project, "developer")
    row = db.get(ProjectVariable, variable_id)
    if row is None or row.project_id != project_id:
        raise HTTPException(status_code=404, detail="Variable not found")
    write_audit(
        db,
        organization_id=project.organization_id,
        actor=user,
        action="variable.delete",
        resource_type="variable",
        resource_id=row.key,
    )
    db.delete(row)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
