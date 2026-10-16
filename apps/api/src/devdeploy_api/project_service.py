"""Organization and project domain logic."""

from __future__ import annotations

import re
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DbSession

from devdeploy_api.audit import write_audit
from devdeploy_api.models import (
    Organization,
    OrganizationMember,
    Project,
    ProjectEnvironment,
    User,
)
from devdeploy_api.rbac import require_project_role

_SLUG_RE = re.compile(r"[^a-z0-9]+")

DEFAULT_ENVS = (
    ("development", False, 1),
    ("staging", False, 1),
    ("production", True, 2),
)


def slugify(value: str) -> str:
    slug = _SLUG_RE.sub("-", value.strip().lower()).strip("-")
    return slug[:80] or "project"


def ensure_personal_org(db: DbSession, user: User) -> Organization:
    membership = db.execute(
        select(OrganizationMember)
        .where(OrganizationMember.user_id == user.id)
        .where(OrganizationMember.role == "owner")
        .limit(1)
    ).scalar_one_or_none()
    if membership:
        org = db.get(Organization, membership.organization_id)
        if org:
            return org

    base = slugify(user.display_name or user.email or f"user-{str(user.id)[:8]}")
    slug = f"{base}-personal"
    existing = db.execute(
        select(Organization).where(Organization.slug == slug)
    ).scalar_one_or_none()
    if existing:
        slug = f"{base}-{str(user.id)[:8]}"

    org = Organization(
        name=f"{user.display_name or 'Personal'} workspace",
        slug=slug,
    )
    db.add(org)
    db.flush()
    db.add(
        OrganizationMember(
            organization_id=org.id,
            user_id=user.id,
            role="owner",
        )
    )
    db.commit()
    db.refresh(org)
    return org


def user_org_ids(db: DbSession, user: User) -> list[uuid.UUID]:
    rows = db.execute(
        select(OrganizationMember.organization_id).where(
            OrganizationMember.user_id == user.id
        )
    ).scalars().all()
    return list(rows)


def list_projects(db: DbSession, user: User) -> list[Project]:
    org_ids = user_org_ids(db, user)
    if not org_ids:
        return []
    return list(
        db.execute(
            select(Project)
            .where(Project.organization_id.in_(org_ids))
            .order_by(Project.created_at.desc())
        ).scalars().all()
    )


def get_project_for_user(
    db: DbSession, user: User, project_id: uuid.UUID
) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    org_ids = user_org_ids(db, user)
    if project.organization_id not in org_ids:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def ensure_default_environments(db: DbSession, project: Project) -> None:
    existing = {
        e.name
        for e in db.execute(
            select(ProjectEnvironment).where(ProjectEnvironment.project_id == project.id)
        ).scalars().all()
    }
    for name, approval, replicas in DEFAULT_ENVS:
        if name in existing:
            continue
        db.add(
            ProjectEnvironment(
                project_id=project.id,
                name=name,
                deploy_branch=project.deploy_branch or "main",
                replicas=replicas if name == "production" else project.replicas or 1,
                approval_required=approval and project.approval_required_prod,
            )
        )


def create_project(
    db: DbSession,
    user: User,
    *,
    name: str,
    slug: str | None,
    description: str | None,
) -> Project:
    org = ensure_personal_org(db, user)
    project_slug = slugify(slug or name)

    conflict = db.execute(
        select(Project).where(
            Project.organization_id == org.id,
            Project.slug == project_slug,
        )
    ).scalar_one_or_none()
    if conflict:
        project_slug = f"{project_slug}-{uuid.uuid4().hex[:6]}"

    project = Project(
        organization_id=org.id,
        owner_user_id=user.id,
        name=name.strip(),
        slug=project_slug,
        description=description.strip() if description else None,
        default_branch="main",
        deploy_branch="main",
        dockerfile_path="Dockerfile",
        container_port=8000,
        health_path="/health",
        auto_deploy=True,
        replicas=1,
    )
    db.add(project)
    try:
        db.flush()
        ensure_default_environments(db, project)
        write_audit(
            db,
            organization_id=org.id,
            actor=user,
            action="project.create",
            resource_type="project",
            resource_id=str(project.id),
            detail=project.name,
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Could not create project (slug conflict)",
        ) from exc
    db.refresh(project)
    return project


def update_project(
    db: DbSession,
    user: User,
    project_id: uuid.UUID,
    **fields: object,
) -> Project:
    project = get_project_for_user(db, user, project_id)
    require_project_role(db, user, project, "developer")

    simple = {
        "name",
        "description",
        "deploy_branch",
        "dockerfile_path",
        "health_path",
        "cpu_request",
        "memory_request",
        "cpu_limit",
        "memory_limit",
    }
    for key in simple:
        val = fields.get(key, ...)
        if val is not ... and val is not None:
            if isinstance(val, str):
                setattr(project, key, val.strip() or None if key == "description" else val.strip())
            else:
                setattr(project, key, val)

    if fields.get("slug", ...) is not ... and fields["slug"] is not None:
        project.slug = slugify(str(fields["slug"]))
    if fields.get("container_port", ...) is not ... and fields["container_port"] is not None:
        project.container_port = int(fields["container_port"])  # type: ignore[arg-type]
    if fields.get("auto_deploy", ...) is not ... and fields["auto_deploy"] is not None:
        project.auto_deploy = bool(fields["auto_deploy"])
    if fields.get("replicas", ...) is not ... and fields["replicas"] is not None:
        project.replicas = int(fields["replicas"])  # type: ignore[arg-type]
    if fields.get("approval_required_prod", ...) is not ... and fields[
        "approval_required_prod"
    ] is not None:
        project.approval_required_prod = bool(fields["approval_required_prod"])
        prod = db.execute(
            select(ProjectEnvironment)
            .where(ProjectEnvironment.project_id == project.id)
            .where(ProjectEnvironment.name == "production")
        ).scalar_one_or_none()
        if prod:
            prod.approval_required = project.approval_required_prod

    ensure_default_environments(db, project)
    write_audit(
        db,
        organization_id=project.organization_id,
        actor=user,
        action="project.update",
        resource_type="project",
        resource_id=str(project.id),
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Project slug already in use in this organization",
        ) from exc
    db.refresh(project)
    return project


def delete_project(db: DbSession, user: User, project_id: uuid.UUID) -> None:
    project = get_project_for_user(db, user, project_id)
    require_project_role(db, user, project, "admin")
    write_audit(
        db,
        organization_id=project.organization_id,
        actor=user,
        action="project.delete",
        resource_type="project",
        resource_id=str(project.id),
        detail=project.name,
    )
    db.delete(project)
    db.commit()
