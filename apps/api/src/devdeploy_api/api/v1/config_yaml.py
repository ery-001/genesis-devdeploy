"""devdeploy.yaml validate + apply."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DbSession

from devdeploy_api.deps import get_current_user, get_db
from devdeploy_api.models import User
from devdeploy_api.project_service import get_project_for_user, update_project
from devdeploy_api.rbac import require_project_role
from devdeploy_api.schemas import (
    DevDeployYamlApplyRequest,
    DevDeployYamlValidateOut,
    DevDeployYamlValidateRequest,
    ProjectOut,
)
from devdeploy_api.yaml_config import parse_devdeploy_yaml, settings_from_parsed

router = APIRouter(prefix="/projects", tags=["devdeploy-yaml"])


@router.post("/{project_id}/devdeploy-yaml/validate", response_model=DevDeployYamlValidateOut)
def validate_yaml(
    project_id: UUID,
    body: DevDeployYamlValidateRequest,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DevDeployYamlValidateOut:
    get_project_for_user(db, user, project_id)
    parsed, errors = parse_devdeploy_yaml(body.yaml_text)
    return DevDeployYamlValidateOut(
        valid=len(errors) == 0,
        errors=errors,
        parsed=settings_from_parsed(parsed) if not errors else parsed,
    )


@router.post("/{project_id}/devdeploy-yaml/apply", response_model=ProjectOut)
def apply_yaml(
    project_id: UUID,
    body: DevDeployYamlApplyRequest,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ProjectOut:
    project = get_project_for_user(db, user, project_id)
    require_project_role(db, user, project, "developer")
    parsed, errors = parse_devdeploy_yaml(body.yaml_text)
    if errors:
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail="; ".join(errors))
    fields = settings_from_parsed(parsed)
    project = update_project(db, user, project_id, **fields)
    return ProjectOut.model_validate(project)
