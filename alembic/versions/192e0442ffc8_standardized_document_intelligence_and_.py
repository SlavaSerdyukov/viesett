"""standardized document intelligence and deterministic rules

Revision ID: 192e0442ffc8
Revises: da321bc669fb
"""

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import uuid4

import sqlalchemy as sa

from alembic import op

revision: str = "192e0442ffc8"
down_revision: str | None = "da321bc669fb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "due_diligence_evaluations",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("evaluation_date", sa.Date(), nullable=False),
        sa.Column("input_hash", sa.String(length=64), nullable=False),
        sa.Column("identity_revision", sa.String(length=64), nullable=True),
        sa.Column("requirements", sa.JSON(), nullable=False),
        sa.Column("finding_ids", sa.JSON(), nullable=False),
        sa.Column("rules", sa.JSON(), nullable=False),
        sa.Column("inputs", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["property_workspaces.id"],
            name=op.f("fk_due_diligence_evaluations_workspace_id_property_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_due_diligence_evaluations")),
    )
    op.create_index(
        op.f("ix_due_diligence_evaluations_workspace_id"),
        "due_diligence_evaluations",
        ["workspace_id"],
        unique=False,
    )
    op.create_table(
        "document_analyses",
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "PENDING",
                "EXTRACTING",
                "READY",
                "OCR_REQUIRED",
                "FAILED",
                "DELETED",
                name="extractionstatus",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("automated_classification", sa.JSON(), nullable=False),
        sa.Column(
            "manual_classification",
            sa.Enum(
                "UNKNOWN",
                "EPC",
                "ASBESTOS_CERTIFICATE",
                "ELECTRICAL_INSPECTION",
                "SOIL_CERTIFICATE",
                name="manualclassification",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=True,
        ),
        sa.Column("correction_recorded", sa.Boolean(), nullable=False),
        sa.Column(
            "effective_classification",
            sa.Enum(
                "UNKNOWN",
                "EPC",
                "ASBESTOS_CERTIFICATE",
                "ELECTRICAL_INSPECTION",
                "SOIL_CERTIFICATE",
                name="analysiskind",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("association", sa.JSON(), nullable=False),
        sa.Column("fields", sa.JSON(), nullable=False),
        sa.Column("evidence_ids", sa.JSON(), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=False),
        sa.Column("parser_version", sa.String(length=80), nullable=False),
        sa.Column("source_sha256", sa.String(length=64), nullable=False),
        sa.Column("artifact_storage_key", sa.String(length=64), nullable=True),
        sa.Column("failure_code", sa.String(length=80), nullable=True),
        sa.Column("retry_eligible", sa.Boolean(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["document_id", "workspace_id"],
            ["property_documents.id", "property_documents.workspace_id"],
            name=op.f("fk_document_analyses_document_id_property_documents"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_document_analyses")),
        sa.UniqueConstraint(
            "document_id", "generation", name=op.f("uq_document_analyses_document_id")
        ),
        sa.UniqueConstraint("id", "workspace_id", name=op.f("uq_document_analyses_id")),
        sa.UniqueConstraint("id", "document_id", "workspace_id", name="uq_analysis_source"),
        sa.CheckConstraint(
            "generation > 0 AND page_count >= 0", name=op.f("ck_document_analyses_analysis_bounds")
        ),
    )
    op.create_index(
        op.f("ix_document_analyses_workspace_id"),
        "document_analyses",
        ["workspace_id"],
        unique=False,
    )
    op.create_table(
        "document_text_artifacts",
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("analysis_id", sa.Uuid(), nullable=False),
        sa.Column("parser_name", sa.String(length=80), nullable=False),
        sa.Column("parser_version", sa.String(length=80), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("storage_key", sa.String(length=64), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["analysis_id", "document_id", "workspace_id"],
            [
                "document_analyses.id",
                "document_analyses.document_id",
                "document_analyses.workspace_id",
            ],
            name=op.f("fk_document_text_artifacts_analysis_id_document_analyses"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["document_id", "workspace_id"],
            ["property_documents.id", "property_documents.workspace_id"],
            name=op.f("fk_document_text_artifacts_document_id_property_documents"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_document_text_artifacts")),
        sa.UniqueConstraint("analysis_id", name=op.f("uq_document_text_artifacts_analysis_id")),
        sa.UniqueConstraint("storage_key", name=op.f("uq_document_text_artifacts_storage_key")),
        sa.CheckConstraint(
            "page_count > 0", name=op.f("ck_document_text_artifacts_artifact_pages")
        ),
    )
    op.create_index(
        op.f("ix_document_text_artifacts_workspace_id"),
        "document_text_artifacts",
        ["workspace_id"],
        unique=False,
    )
    op.create_check_constraint(
        op.f("ck_evidence_items_document_extractor_provenance"),
        "evidence_items",
        "source_version IS NULL OR source_version NOT LIKE 'document-extractor:%' OR "
        "(authority = 'DOCUMENTED' AND source_type = 'DOCUMENT' AND document_id IS NOT NULL "
        "AND source_locator ->> 'document_id' IS NOT NULL "
        "AND source_locator ->> 'document_id' = document_id::text "
        "AND source_locator ->> 'page' IS NOT NULL "
        "AND source_locator ->> 'parser_version' IS NOT NULL)",
    )
    policies = sa.table(
        "policy_versions",
        sa.column("id", sa.Uuid()),
        sa.column("policy_type", sa.String()),
        sa.column("version", sa.String()),
        sa.column("text", sa.String()),
        sa.column("current", sa.Boolean()),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )
    bind = op.get_bind()
    previous = bind.execute(
        sa.select(policies.c.text).where(
            policies.c.policy_type == "PRIVACY_NOTICE",
            policies.c.version == "2026-11-11-m2",
        )
    ).scalar_one()
    bind.execute(
        sa.update(policies).where(policies.c.policy_type == "PRIVACY_NOTICE").values(current=False)
    )
    existing = bind.execute(
        sa.select(policies.c.id).where(
            policies.c.policy_type == "PRIVACY_NOTICE",
            policies.c.version == "2026-11-12-m3",
        )
    ).scalar_one_or_none()
    if existing is None:
        bind.execute(
            sa.insert(policies).values(
                id=uuid4(),
                policy_type="PRIVACY_NOTICE",
                version="2026-11-12-m3",
                current=True,
                created_at=datetime.now(UTC),
                text=previous + "\nRequested local PDF text extraction creates "
                "private page-level text artifacts, "
                "structured DOCUMENTED facts, classification/association history "
                "and deterministic "
                "versioned regulatory evaluations. No OCR, AI, training or external "
                "document processor is required. Source deletion also erases derived text "
                "and affected evaluation inputs. "
                "Rules assist document review and do not provide legal transaction approval.",
            )
        )
    else:
        bind.execute(sa.update(policies).where(policies.c.id == existing).values(current=True))


def downgrade() -> None:
    bind = op.get_bind()
    if bind.execute(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM document_analyses) OR "
            "EXISTS (SELECT 1 FROM due_diligence_evaluations) OR "
            "EXISTS (SELECT 1 FROM evidence_items WHERE "
            "source_version LIKE 'document-extractor:%') OR "
            "EXISTS (SELECT 1 FROM findings WHERE provenance ->> 'source' = 'viesett.rules')"
        )
    ).scalar_one():
        raise RuntimeError(
            "Remove M3 dossier data through authenticated deletion before downgrade; "
            "private artifacts must not be orphaned"
        )
    op.execute(
        sa.text("UPDATE policy_versions SET current = false WHERE policy_type = 'PRIVACY_NOTICE'")
    )
    op.execute(
        sa.text(
            "UPDATE policy_versions SET current = true WHERE "
            "policy_type = 'PRIVACY_NOTICE' AND version = '2026-11-11-m2'"
        )
    )
    op.drop_constraint(
        op.f("ck_evidence_items_document_extractor_provenance"), "evidence_items", type_="check"
    )
    op.drop_index(
        op.f("ix_document_text_artifacts_workspace_id"), table_name="document_text_artifacts"
    )
    op.drop_table("document_text_artifacts")
    op.drop_index(op.f("ix_document_analyses_workspace_id"), table_name="document_analyses")
    op.drop_table("document_analyses")
    op.drop_index(
        op.f("ix_due_diligence_evaluations_workspace_id"), table_name="due_diligence_evaluations"
    )
    op.drop_table("due_diligence_evaluations")
