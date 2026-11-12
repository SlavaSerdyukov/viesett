"""Migration sentinel; dedicated disposable PostgreSQL only, no source bytes/network."""

import asyncio
import json
import sys
from datetime import date
from pathlib import Path
from uuid import UUID

from sqlalchemy import select, text

from viesett.core.config import Settings
from viesett.db.intelligence_models import DueDiligenceEvaluation
from viesett.db.models import (
    Account,
    EvidenceItem,
    Finding,
    FindingEvidence,
    PolicyVersion,
    PropertyDocument,
    PropertyWorkspace,
    UserPolicyAcknowledgement,
    utcnow,
)
from viesett.db.property_models import PropertyIdentity, PropertyParcel
from viesett.db.session import create_engine, session_factory
from viesett.domain.property import ResolutionStatus
from viesett.domain.types import Authority, DocumentKind, DocumentStatus, Severity, SourceType

STATE = Path(".local/m3-migration-sentinel.json")


async def run(mode: str) -> None:
    engine = create_engine(Settings())
    try:
        async with session_factory(engine)() as db:
            if mode == "seed":
                account = Account()
                db.add(account)
                await db.flush()
                workspace = PropertyWorkspace(owner_user_id=account.id)
                db.add(workspace)
                await db.flush()
                now = utcnow()
                identity = PropertyIdentity(
                    workspace_id=workspace.id,
                    input_address_query="Migrationstraat 42",
                    property_key="synthetic-m3-upgrade",
                    revision="a" * 64,
                    resolved_at=now,
                    resolution_status=ResolutionStatus.RESOLVED,
                    selected_unit_official_id=None,
                    official_id="900000001",
                    source_uri="https://data.vlaanderen.be/id/adres/900000001",
                    source_version="synthetic-v1",
                    retrieved_at=now,
                    status="inGebruik",
                    native_geometry=None,
                    canonical_address="Migrationstraat 42, 9000 Gent",
                    street_name="Migrationstraat",
                    house_number="42",
                    box_number=None,
                    postal_code="9000",
                    municipality="Gent",
                    municipality_code="44021",
                )
                db.add(identity)
                await db.flush()
                for identifier in ["11001B0001-00S000", "11001B0009-00G004"]:
                    db.add(
                        PropertyParcel(
                            workspace_id=workspace.id,
                            official_id=identifier,
                            source_uri="https://data.vlaanderen.be/id/perceel/" + identifier,
                            source_version="synthetic-v1",
                            retrieved_at=now,
                            status="gerealiseerd",
                            native_geometry=None,
                            capakey=identifier.replace("-", "/"),
                            address_official_ids=["900000001"],
                        )
                    )
                document = PropertyDocument(
                    workspace_id=workspace.id,
                    original_filename="synthetic-migration.pdf",
                    media_type="application/pdf",
                    size_bytes=42,
                    sha256="b" * 64,
                    storage_key="c" * 64,
                    document_kind=DocumentKind.EPC,
                    status=DocumentStatus.READY,
                    safety_reason="synthetic_metadata_only",
                )
                db.add(document)
                await db.flush()
                evidence = EvidenceItem(
                    workspace_id=workspace.id,
                    document_id=document.id,
                    key="document.synthetic",
                    typed_value={"kind": "text", "value": "M2 sentinel"},
                    source_type=SourceType.DOCUMENT,
                    authority=Authority.DOCUMENTED,
                    source_locator={"page": 1},
                    confidence=1,
                    observed_at=now,
                )
                db.add(evidence)
                await db.flush()
                finding = Finding(
                    workspace_id=workspace.id,
                    code="M2_SENTINEL",
                    severity=Severity.INFO,
                    summary="Synthetic migration finding",
                    details=None,
                    provenance={"method": "manual", "source": "migration-sentinel", "version": "1"},
                )
                db.add(finding)
                await db.flush()
                db.add(
                    FindingEvidence(
                        workspace_id=workspace.id, finding_id=finding.id, evidence_id=evidence.id
                    )
                )
                for version in ["2026-11-11", "2026-11-11-m2"]:
                    policy = await db.scalar(
                        select(PolicyVersion).where(
                            PolicyVersion.policy_type == "PRIVACY_NOTICE",
                            PolicyVersion.version == version,
                        )
                    )
                    assert policy is not None
                    db.add(
                        UserPolicyAcknowledgement(user_id=account.id, policy_version_id=policy.id)
                    )
                await db.commit()
                await asyncio.to_thread(STATE.parent.mkdir, parents=True, exist_ok=True)
                await asyncio.to_thread(
                    STATE.write_text,
                    json.dumps(
                        {
                            "account": str(account.id),
                            "workspace": str(workspace.id),
                            "document": str(document.id),
                            "evidence": str(evidence.id),
                            "finding": str(finding.id),
                        }
                    ),
                )
                print(
                    "Seeded M2 property, two parcels, document, page evidence, "
                    "finding and old acknowledgements"
                )
            elif mode == "verify":
                state = json.loads(await asyncio.to_thread(STATE.read_text))
                saved_identity = await db.get(PropertyIdentity, UUID(state["workspace"]))
                assert (
                    saved_identity is not None
                    and saved_identity.canonical_address == "Migrationstraat 42, 9000 Gent"
                )
                assert (
                    len(
                        (
                            await db.scalars(
                                select(PropertyParcel).where(
                                    PropertyParcel.workspace_id == saved_identity.workspace_id
                                )
                            )
                        ).all()
                    )
                    == 2
                )
                saved_document = await db.get(PropertyDocument, UUID(state["document"]))
                saved_evidence = await db.get(EvidenceItem, UUID(state["evidence"]))
                assert saved_document is not None and saved_document.sha256 == "b" * 64
                assert saved_evidence is not None and saved_evidence.source_locator == {"page": 1}
                assert await db.get(Finding, UUID(state["finding"])) is not None
                assert (
                    len(
                        (
                            await db.scalars(
                                select(UserPolicyAcknowledgement).where(
                                    UserPolicyAcknowledgement.user_id == UUID(state["account"])
                                )
                            )
                        ).all()
                    )
                    == 2
                )
                current = await db.scalar(
                    select(PolicyVersion).where(
                        PolicyVersion.policy_type == "PRIVACY_NOTICE",
                        PolicyVersion.current.is_(True),
                    )
                )
                assert current is not None and current.version == "2026-11-12-m3"
                checks = await db.scalar(
                    text(
                        "SELECT count(*) FROM pg_constraint WHERE conname IN "
                        "('ck_document_analyses_analysis_bounds', "
                        "'ck_document_text_artifacts_artifact_pages', "
                        "'ck_evidence_items_document_extractor_provenance')"
                    )
                )
                assert checks == 3
                saved_account = await db.get(Account, UUID(state["account"]))
                assert saved_account is not None
                await db.delete(saved_account)
                await db.commit()
                print(
                    "M2 property/document/evidence/finding/acknowledgements preserved; "
                    "M3 constraints and notice verified"
                )
            elif mode == "guard":
                account = Account()
                db.add(account)
                await db.flush()
                workspace = PropertyWorkspace(owner_user_id=account.id)
                db.add(workspace)
                await db.flush()
                blocker = DueDiligenceEvaluation(
                    workspace_id=workspace.id,
                    evaluation_date=date(2026, 11, 12),
                    input_hash="d" * 64,
                    identity_revision=None,
                    requirements=[],
                    finding_ids=[],
                    rules=[],
                    inputs={},
                )
                db.add(blocker)
                await db.commit()
                process = await asyncio.create_subprocess_exec(
                    sys.executable,
                    "-m",
                    "alembic",
                    "downgrade",
                    "da321bc669fb",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                _, error = await process.communicate()
                assert process.returncode != 0 and b"Remove M3 dossier data" in error
                assert (
                    await db.scalar(text("SELECT version_num FROM alembic_version"))
                    == "192e0442ffc8"
                )
                assert await db.get(DueDiligenceEvaluation, blocker.id) is not None
                await db.delete(account)
                await db.commit()
                print("Downgrade rejected nonempty M3 state without changing revision or data")
            else:
                raise ValueError("Choose seed, verify or guard")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run(sys.argv[1]))
