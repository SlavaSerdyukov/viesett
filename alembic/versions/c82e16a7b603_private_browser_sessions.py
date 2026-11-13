"""Private browser sessions and explicitly unverified buyer context.

Revision ID: c82e16a7b603
Revises: f51e9bf1a005
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c82e16a7b603"
down_revision: str | None = "f51e9bf1a005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint(op.f("uq_api_tokens_id"), "api_tokens", ["id", "user_id"])
    op.create_table(
        "browser_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("api_token_id", sa.Uuid(), nullable=False),
        sa.Column("secret_hash", sa.String(64), nullable=False),
        sa.Column("csrf_token", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["accounts.id"],
            name=op.f("fk_browser_sessions_user_id_accounts"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["api_token_id", "user_id"],
            ["api_tokens.id", "api_tokens.user_id"],
            name=op.f("fk_browser_sessions_api_token_id_api_tokens"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_browser_sessions")),
        sa.UniqueConstraint("secret_hash", name=op.f("uq_browser_sessions_secret_hash")),
    )
    op.create_index(op.f("ix_browser_sessions_user_id"), "browser_sessions", ["user_id"])
    op.create_index(op.f("ix_browser_sessions_api_token_id"), "browser_sessions", ["api_token_id"])
    op.drop_constraint(op.f("ck_evidence_items_authority"), "evidence_items", type_="check")
    op.create_check_constraint(
        "authority",
        "evidence_items",
        "authority IN ('OFFICIAL', 'DOCUMENTED', 'INFERRED', 'UNVERIFIED')",
    )
    op.create_check_constraint(
        "user_context_unverified",
        "evidence_items",
        "authority != 'UNVERIFIED' OR (source_type = 'MANUAL' "
        "AND document_id IS NULL AND provider IS NULL)",
    )


def downgrade() -> None:
    if (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT EXISTS (SELECT 1 FROM browser_sessions) OR "
                "EXISTS (SELECT 1 FROM evidence_items WHERE authority = 'UNVERIFIED')"
            )
        )
        .scalar_one()
    ):
        raise RuntimeError("Remove private browser sessions and buyer context before M6 downgrade")
    op.drop_constraint(
        op.f("ck_evidence_items_user_context_unverified"), "evidence_items", type_="check"
    )
    op.drop_constraint(op.f("ck_evidence_items_authority"), "evidence_items", type_="check")
    op.create_check_constraint(
        "authority", "evidence_items", "authority IN ('OFFICIAL', 'DOCUMENTED', 'INFERRED')"
    )
    op.drop_table("browser_sessions")
    op.drop_constraint(op.f("uq_api_tokens_id"), "api_tokens", type_="unique")
