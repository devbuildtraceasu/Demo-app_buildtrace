"""Project routes."""

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from sqlmodel import select

from api.dependencies import CurrentUser, SessionDep
from api.schemas.project import ProjectCreate, ProjectResponse, ProjectUpdate

router = APIRouter()


# SQLModel for Project (matches Prisma schema)
from sqlmodel import Field, SQLModel


class Project(SQLModel, table=True):
    """Project database model."""

    __tablename__ = "projects"

    id: str = Field(primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    deleted_at: datetime | None = None
    organization_id: str
    name: str
    description: str | None = None


def generate_cuid() -> str:
    """Generate a CUID-like ID."""
    import secrets
    import time

    timestamp = hex(int(time.time() * 1000))[2:]
    random_part = secrets.token_hex(8)
    return f"c{timestamp}{random_part}"[:25]


@router.get("", response_model=list[ProjectResponse])
async def list_projects(session: SessionDep, user: CurrentUser):
    """List all projects for the current user's organization."""
    org_id = user.get("organization_id", "default-org")
    statement = select(Project).where(
        Project.organization_id == org_id,
        Project.deleted_at.is_(None),
    )
    projects = session.exec(statement).all()

    return [
        ProjectResponse(
            id=p.id,
            name=p.name,
            description=p.description,
            organization_id=p.organization_id,
            created_at=p.created_at,
            updated_at=p.updated_at,
        )
        for p in projects
    ]


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    project_data: ProjectCreate,
    session: SessionDep,
    user: CurrentUser,
):
    """Create a new project."""
    org_id = project_data.organization_id or user.get("organization_id", "default-org")

    project = Project(
        id=generate_cuid(),
        name=project_data.name,
        description=project_data.description,
        organization_id=org_id,
    )

    session.add(project)
    session.commit()
    session.refresh(project)

    return ProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        organization_id=project.organization_id,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: str, session: SessionDep, user: CurrentUser):
    """Get a project by ID."""
    project = session.get(Project, project_id)

    if not project or project.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    return ProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        organization_id=project.organization_id,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    project_data: ProjectUpdate,
    session: SessionDep,
    user: CurrentUser,
):
    """Update a project."""
    project = session.get(Project, project_id)

    if not project or project.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    if project_data.name is not None:
        project.name = project_data.name
    if project_data.description is not None:
        project.description = project_data.description

    project.updated_at = datetime.now(timezone.utc)
    session.add(project)
    session.commit()
    session.refresh(project)

    return ProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        organization_id=project.organization_id,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(project_id: str, session: SessionDep, user: CurrentUser):
    """Soft delete a project."""
    project = session.get(Project, project_id)

    if not project or project.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    project.deleted_at = datetime.now(timezone.utc)
    project.updated_at = datetime.now(timezone.utc)
    session.add(project)
    session.commit()

    return None

