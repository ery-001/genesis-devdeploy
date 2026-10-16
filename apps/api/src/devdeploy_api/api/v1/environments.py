"""Per-project environments (development / staging / production)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from devdeploy_api.deps import get_current_user, get_db
from devdeploy_api.models import ProjectEnvironment, User
from devdeploy_api.project_service import (
    ensure_default_environments,
    get_project_for_user,
)
from devdeploy_api.rbac import require_project_role
from devdeploy_api.schemas import EnvironmentOut, EnvironmentUpdate

router = APIRouter(prefix="/projects", tags=["environments"])


@router.get("/{project_id}/environments", response_model=list[EnvironmentOut])
def list_environments(
    project_id: UUID,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[EnvironmentOut]:
    project = get_project_for_user(db, user, project_id)
    ensure_default_environments(db, project)
    db.commit()
    rows = db.execute(
        select(ProjectEnvironment)
        .where(ProjectEnvironment.project_id == project_id)
        .order_by(ProjectEnvironment.name.asc())
    ).scalars().all()
    return [EnvironmentOut.model_validate(r) for r in rows]


@router.patch(
    "/{project_id}/environments/{env_id}",
    response_model=EnvironmentOut,
)
def patch_environment(
    project_id: UUID,
    env_id: UUID,
    body: EnvironmentUpdate,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> EnvironmentOut:
    project = get_project_for_user(db, user, project_id)
    require_project_role(db, user, project, "admin")
    env = db.get(ProjectEnvironment, env_id)
    if env is None or env.project_id != project_id:
        raise HTTPException(status_code=404, detail="Environment not found")
    if body.deploy_branch is not None:
        env.deploy_branch = body.deploy_branch.strip() or None
    if body.replicas is not None:
        env.replicas = body.replicas
    if body.approval_required is not None:
        env.approval_required = body.approval_required
        if env.name == "production":
            project.approval_required_prod = body.approval_required
    db.commit()
    db.refresh(env)
    return EnvironmentOut.model_validate(env)
