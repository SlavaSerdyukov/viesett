"""co ownership and cross document intelligence

Revision ID: d64802d3610f
Revises: 192e0442ffc8
"""

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import uuid4

import sqlalchemy as sa

from alembic import op

revision: str = "d64802d3610f"
down_revision: str | None = "192e0442ffc8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD_DOCUMENT_KINDS = (
    "UNKNOWN",
    "LISTING",
    "EPC",
    "ASBESTOS_CERTIFICATE",
    "ELECTRICAL_INSPECTION",
    "SOIL_CERTIFICATE",
    "URBAN_PLANNING",
    "SYNDIC_MINUTES",
    "CO_OWNERSHIP_STATUTES",
    "RESERVE_FUND",
    "OTHER_PROPERTY_DOCUMENT",
)
OLD_ANALYSIS_KINDS = (
    "UNKNOWN",
    "EPC",
    "ASBESTOS_CERTIFICATE",
    "ELECTRICAL_INSPECTION",
    "SOIL_CERTIFICATE",
)
CO_KINDS = (
    "SYNDIC_INFORMATION",
    "AGM_MINUTES",
    "EXTRAORDINARY_AGM_MINUTES",
    "BASIS_DEED",
    "CO_OWNERSHIP_REGULATIONS",
    "INTERNAL_RULES",
    "PERIODIC_CHARGE_STATEMENT",
    "BALANCE_SHEET",
    "CAPITAL_CALL",
    "RESERVE_FUND_STATEMENT",
    "OTHER_CO_OWNERSHIP_DOCUMENT",
)


def upgrade() -> None:
    op.create_table(
        "co_ownership_evaluations",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("evaluation_date", sa.Date(), nullable=False),
        sa.Column("input_hash", sa.String(length=64), nullable=False),
        sa.Column("identity_revision", sa.String(length=64), nullable=True),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("inputs", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["property_workspaces.id"],
            name=op.f("fk_co_ownership_evaluations_workspace_id_property_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_co_ownership_evaluations")),
        sa.UniqueConstraint("id", "workspace_id", name=op.f("uq_co_ownership_evaluations_id")),
    )
    op.create_index(
        op.f("ix_co_ownership_evaluations_workspace_id"),
        "co_ownership_evaluations",
        ["workspace_id"],
        unique=False,
    )
    op.create_table(
        "co_ownership_identities",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("evaluation_id", sa.Uuid(), nullable=False),
        sa.Column("association_name", sa.String(length=200), nullable=True),
        sa.Column("enterprise_number", sa.String(length=10), nullable=True),
        sa.Column("building_address", sa.String(length=300), nullable=True),
        sa.Column("syndic_name", sa.String(length=200), nullable=True),
        sa.Column("syndic_enterprise_number", sa.String(length=10), nullable=True),
        sa.Column("lot_identifier", sa.String(length=60), nullable=True),
        sa.Column("private_unit_designation", sa.String(length=100), nullable=True),
        sa.Column("ownership_share", sa.JSON(), nullable=True),
        sa.Column("attached_lots", sa.JSON(), nullable=False),
        sa.Column("source_document_ids", sa.JSON(), nullable=False),
        sa.Column("evidence_ids", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["evaluation_id", "workspace_id"],
            ["co_ownership_evaluations.id", "co_ownership_evaluations.workspace_id"],
            name=op.f("fk_co_ownership_identities_evaluation_id_co_ownership_evaluations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["property_workspaces.id"],
            name=op.f("fk_co_ownership_identities_workspace_id_property_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("workspace_id", name=op.f("pk_co_ownership_identities")),
    )
    op.create_table(
        "planned_works",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("evaluation_id", sa.Uuid(), nullable=False),
        sa.Column("work_key", sa.String(length=80), nullable=False),
        sa.Column("decision_status", sa.String(length=30), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["evaluation_id", "workspace_id"],
            ["co_ownership_evaluations.id", "co_ownership_evaluations.workspace_id"],
            name=op.f("fk_planned_works_evaluation_id_co_ownership_evaluations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["property_workspaces.id"],
            name=op.f("fk_planned_works_workspace_id_property_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_planned_works")),
    )
    op.create_index(
        op.f("ix_planned_works_workspace_id"), "planned_works", ["workspace_id"], unique=False
    )
    op.add_column("document_analyses", sa.Column("co_metadata", sa.JSON(), nullable=True))
    replace_kind(
        "property_documents", "document_kind", "documentkind", OLD_DOCUMENT_KINDS + CO_KINDS
    )
    replace_kind(
        "document_analyses",
        "effective_classification",
        "analysiskind",
        OLD_ANALYSIS_KINDS + CO_KINDS,
    )
    replace_kind(
        "document_analyses",
        "manual_classification",
        "manualclassification",
        OLD_ANALYSIS_KINDS + CO_KINDS,
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
            policies.c.version == "2026-11-12-m3",
        )
    ).scalar_one()
    bind.execute(
        sa.update(policies).where(policies.c.policy_type == "PRIVACY_NOTICE").values(current=False)
    )
    existing = bind.execute(
        sa.select(policies.c.id).where(
            policies.c.policy_type == "PRIVACY_NOTICE", policies.c.version == "2026-11-12-m4"
        )
    ).scalar_one_or_none()
    if existing is None:
        bind.execute(
            sa.insert(policies).values(
                id=uuid4(),
                policy_type="PRIVACY_NOTICE",
                version="2026-11-12-m4",
                current=True,
                created_at=datetime.now(UTC),
                text=previous
                + "\nRequested apartment review locally derives VME/ACP entity identity, "
                "documented lot shares, fund/charge amounts, meeting decisions, works, calls and "
                "property-related litigation categories. Attendance lists, private contacts, "
                "individual bank details and unrelated personal disputes are not structured. "
                "Versioned cross-document checks, proportional estimates "
                "and buyer questions "
                "retain source references and history; estimates do not determine legal payment "
                "responsibility. Nothing is sent automatically and "
                "no new external processor is used.",
            )
        )
    else:
        bind.execute(sa.update(policies).where(policies.c.id == existing).values(current=True))


def replace_kind(table: str, column: str, name: str, values: tuple[str, ...]) -> None:
    constraint = op.f("ck_" + table + "_" + name)
    op.drop_constraint(constraint, table, type_="check")
    op.alter_column(table, column, type_=sa.String(max(map(len, values))))
    condition = column + " IN (" + ", ".join(repr(value) for value in values) + ")"
    op.create_check_constraint(constraint, table, condition)


def downgrade() -> None:
    bind = op.get_bind()
    kinds = ", ".join(repr(value) for value in CO_KINDS)
    if bind.execute(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM co_ownership_evaluations) OR "
            "EXISTS (SELECT 1 FROM property_documents WHERE document_kind IN (" + kinds + ")) OR "
            "EXISTS (SELECT 1 FROM document_analyses WHERE co_metadata IS NOT NULL OR "
            "effective_classification IN ("
            + kinds
            + ") OR manual_classification IN ("
            + kinds
            + ")) OR "
            "EXISTS (SELECT 1 FROM evidence_items WHERE source_version LIKE '%co-ownership:%') OR "
            "EXISTS (SELECT 1 FROM findings WHERE provenance ->> 'source' = 'viesett.coownership')"
        )
    ).scalar_one():
        raise RuntimeError("Remove M4 dossier data through authenticated deletion before downgrade")
    op.execute(
        sa.text("UPDATE policy_versions SET current = false WHERE policy_type = 'PRIVACY_NOTICE'")
    )
    op.execute(
        sa.text(
            "UPDATE policy_versions SET current = true WHERE policy_type = 'PRIVACY_NOTICE' "
            "AND version = '2026-11-12-m3'"
        )
    )
    replace_kind("property_documents", "document_kind", "documentkind", OLD_DOCUMENT_KINDS)
    replace_kind(
        "document_analyses", "effective_classification", "analysiskind", OLD_ANALYSIS_KINDS
    )
    replace_kind(
        "document_analyses", "manual_classification", "manualclassification", OLD_ANALYSIS_KINDS
    )
    op.drop_column("document_analyses", "co_metadata")
    op.drop_table("planned_works")
    op.drop_table("co_ownership_identities")
    op.drop_table("co_ownership_evaluations")
