from uuid import UUID

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from viesett.db.models import Base


class DemoWorkspace(Base):
    """Persistent synthetic-data label; cannot be submitted through workspace DTOs."""

    __tablename__ = "demo_workspaces"
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("property_workspaces.id", ondelete="CASCADE"), primary_key=True
    )
