"""Product demo marker; no historical migration changes.

Revision ID: f51e9bf1a005
Revises: d64802d3610f
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f51e9bf1a005"
down_revision: str | None = "d64802d3610f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "demo_workspaces",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["property_workspaces.id"],
            name=op.f("fk_demo_workspaces_workspace_id_property_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("workspace_id", name=op.f("pk_demo_workspaces")),
    )


def downgrade() -> None:
    if op.get_bind().execute(sa.text("SELECT EXISTS (SELECT 1 FROM demo_workspaces)")).scalar_one():
        raise RuntimeError("Delete demo workspaces before removing their demo marker")
    op.drop_table("demo_workspaces")
