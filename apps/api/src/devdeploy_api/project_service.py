"""Organization and project domain logic."""

from __future__ import annotations

import re
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DbSession

from devdeploy_api.models import Organization, OrganizationMember, Project, User

_SLUG_RE = re.compile(r"[^a-z0-9]+")


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
    # Ensure unique org slug
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

    # Disambiguate within org
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
    )
    db.add(project)
    try:
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
    *,
    name: str | None,
    slug: str | None,
    description: str | None,
    deploy_branch: str | None = None,
    dockerfile_path: str | None = None,
) -> Project:
    project = get_project_for_user(db, user, project_id)
    if name is not None:
        project.name = name.strip()
    if slug is not None:
        project.slug = slugify(slug)
    if description is not None:
        project.description = description.strip() or None
    if deploy_branch is not None:
        project.deploy_branch = deploy_branch.strip() or None
    if dockerfile_path is not None:
        project.dockerfile_path = dockerfile_path.strip() or None
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
    db.delete(project)
    db.commit()
