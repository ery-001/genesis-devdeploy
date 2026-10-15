"""Project CRUD routes (scoped to the signed-in user's orgs)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session as DbSession

from devdeploy_api import project_service
from devdeploy_api.deps import get_current_user, get_db
from devdeploy_api.models import User
from devdeploy_api.schemas import ProjectCreate, ProjectOut, ProjectUpdate

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=list[ProjectOut])
def list_projects(
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ProjectOut]:
    return [
        ProjectOut.model_validate(p)
        for p in project_service.list_projects(db, user)
    ]


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(
    body: ProjectCreate,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ProjectOut:
    project = project_service.create_project(
        db,
        user,
        name=body.name,
        slug=body.slug,
        description=body.description,
    )
    return ProjectOut.model_validate(project)


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(
    project_id: UUID,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ProjectOut:
    project = project_service.get_project_for_user(db, user, project_id)
    return ProjectOut.model_validate(project)


@router.patch("/{project_id}", response_model=ProjectOut)
def patch_project(
    project_id: UUID,
    body: ProjectUpdate,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ProjectOut:
    project = project_service.update_project(
        db,
        user,
        project_id,
        name=body.name,
        slug=body.slug,
        description=body.description,
    )
    return ProjectOut.model_validate(project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: UUID,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    project_service.delete_project(db, user, project_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
