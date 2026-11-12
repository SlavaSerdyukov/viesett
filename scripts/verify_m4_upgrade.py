"""M3 -> M4 preservation/rollback sentinel. Dedicated disposable PostgreSQL only."""

import asyncio
import hashlib
import json
import sys
from datetime import date
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import delete, insert, select, text, update

from viesett.core.config import Settings
from viesett.db.coownership_models import CoOwnershipEvaluation
from viesett.db.intelligence_models import (
    DocumentAnalysis,
    DocumentTextArtifact,
    DueDiligenceEvaluation,
)
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
from viesett.db.session import create_engine, session_factory
from viesett.domain.intelligence import AnalysisKind
from viesett.domain.types import Authority, DocumentKind, DocumentStatus, Severity, SourceType
from viesett.storage.private import LocalPrivateStorage

STATE = Path(".local/m4-migration-sentinel.json")
SOURCE = b"%PDF-synthetic-M3-preservation-only"
ARTIFACT = b'{"pages":[{"number":1,"text":"Synthetic EPC sentinel"}]}'
FIELDS = [
    {
        "key": "document.epc.label",
        "value_kind": "epc_label",
        "value": "D",
        "page": 1,
        "start": 0,
        "end": 3,
        "parser_version": "epc:1.0.0",
    }
]


async def run(mode: str) -> None:
    engine = create_engine(Settings())
    storage = LocalPrivateStorage(Path(".local/m4-migration-storage"))
    try:
        async with session_factory(engine)() as db:
            if mode == "seed":
                assert (
                    await db.scalar(text("SELECT version_num FROM alembic_version"))
                    == "192e0442ffc8"
                )
                account = Account()
                db.add(account)
                await db.flush()
                workspace = PropertyWorkspace(owner_user_id=account.id)
                db.add(workspace)
                await db.flush()
                source_key, artifact_key = storage.new_key(), storage.new_key()
                storage.put(source_key, SOURCE)
                storage.put(artifact_key, ARTIFACT)
                document = PropertyDocument(
                    workspace_id=workspace.id,
                    original_filename="synthetic-m3.pdf",
                    media_type="application/pdf",
                    size_bytes=len(SOURCE),
                    sha256=hashlib.sha256(SOURCE).hexdigest(),
                    storage_key=source_key,
                    document_kind=DocumentKind.EPC,
                    status=DocumentStatus.READY,
                    safety_reason="synthetic_metadata_sentinel",
                )
                db.add(document)
                await db.flush()
                analysis_id = uuid4()
                # Core INSERT omits the M4-only column while running on M3 schema.
                await db.execute(
                    insert(DocumentAnalysis).values(
                        id=analysis_id,
                        created_at=utcnow(),
                        document_id=document.id,
                        workspace_id=workspace.id,
                        generation=1,
                        status="READY",
                        automated_classification={
                            "predicted_kind": "EPC",
                            "classifier_version": "signals:1.0.0",
                        },
                        manual_classification=None,
                        correction_recorded=False,
                        effective_classification="EPC",
                        association={"status": "MATCHED", "reason": "Synthetic migration sentinel"},
                        fields=FIELDS,
                        evidence_ids=[],
                        page_count=1,
                        parser_version="epc:1.0.0",
                        source_sha256=document.sha256,
                        artifact_storage_key=artifact_key,
                        failure_code=None,
                        retry_eligible=False,
                        completed_at=utcnow(),
                    )
                )
                artifact = DocumentTextArtifact(
                    document_id=document.id,
                    workspace_id=workspace.id,
                    analysis_id=analysis_id,
                    parser_name="pypdf",
                    parser_version="pypdf-text:1.0.0",
                    page_count=1,
                    content_hash=hashlib.sha256(ARTIFACT).hexdigest(),
                    storage_key=artifact_key,
                )
                evidence = EvidenceItem(
                    workspace_id=workspace.id,
                    document_id=document.id,
                    key="document.epc.label",
                    typed_value={"kind": "epc_label", "value": "D"},
                    source_type=SourceType.DOCUMENT,
                    authority=Authority.DOCUMENTED,
                    source_version="document-extractor:epc:1.0.0",
                    source_locator={
                        "document_id": str(document.id),
                        "page": 1,
                        "start_offset": 0,
                        "end_offset": 3,
                        "parser_version": "epc:1.0.0",
                    },
                    confidence=1,
                    observed_at=utcnow(),
                )
                db.add_all([artifact, evidence])
                await db.flush()
                await db.execute(
                    update(DocumentAnalysis)
                    .where(DocumentAnalysis.id == analysis_id)
                    .values(evidence_ids=[str(evidence.id)])
                )
                finding = Finding(
                    workspace_id=workspace.id,
                    code="M3_PRESERVATION_SENTINEL",
                    severity=Severity.REVIEW,
                    summary="Synthetic M3 rule result",
                    details=None,
                    provenance={
                        "method": "deterministic",
                        "source": "viesett.rules",
                        "version": "1.0.0",
                    },
                )
                db.add(finding)
                await db.flush()
                db.add(
                    FindingEvidence(
                        workspace_id=workspace.id, finding_id=finding.id, evidence_id=evidence.id
                    )
                )
                evaluation = DueDiligenceEvaluation(
                    workspace_id=workspace.id,
                    evaluation_date=date(2026, 11, 12),
                    input_hash="d" * 64,
                    identity_revision=None,
                    requirements=[],
                    finding_ids=[str(finding.id)],
                    rules=[],
                    inputs={"synthetic": True},
                )
                db.add(evaluation)
                policy = await db.scalar(
                    select(PolicyVersion).where(
                        PolicyVersion.policy_type == "PRIVACY_NOTICE",
                        PolicyVersion.version == "2026-11-12-m3",
                    )
                )
                assert policy is not None
                db.add(UserPolicyAcknowledgement(user_id=account.id, policy_version_id=policy.id))
                await db.commit()
                await asyncio.to_thread(STATE.parent.mkdir, parents=True, exist_ok=True)
                await asyncio.to_thread(
                    STATE.write_text,
                    json.dumps(
                        {
                            "account": str(account.id),
                            "workspace": str(workspace.id),
                            "document": str(document.id),
                            "analysis": str(analysis_id),
                            "evidence": str(evidence.id),
                            "finding": str(finding.id),
                            "evaluation": str(evaluation.id),
                            "source_key": source_key,
                            "artifact_key": artifact_key,
                            "policy_hash": hashlib.sha256(policy.text.encode()).hexdigest(),
                        }
                    ),
                )
                print(
                    "Seeded M3 analysis, private bytes/artifact, evidence, rule finding, "
                    "evaluation and acknowledgement"
                )
                return
            state = json.loads(await asyncio.to_thread(STATE.read_text))
            wid, aid = UUID(state["workspace"]), UUID(state["analysis"])
            if mode in {"verify", "verify-m3"}:
                row = (
                    await db.execute(
                        text(
                            "SELECT effective_classification, fields, evidence_ids, "
                            "artifact_storage_key "
                            "FROM document_analyses WHERE id = :id"
                        ),
                        {"id": aid},
                    )
                ).one()
                assert row[0] == "EPC" and row[1] == FIELDS and row[2] == [state["evidence"]]
                assert row[3] == state["artifact_key"]
                assert storage.read(state["source_key"]) == SOURCE
                assert storage.read(state["artifact_key"]) == ARTIFACT
                saved_evidence = await db.get(EvidenceItem, UUID(state["evidence"]))
                assert (
                    saved_evidence
                    and saved_evidence.authority == Authority.DOCUMENTED
                    and saved_evidence.source_locator["page"] == 1
                )
                assert await db.get(Finding, UUID(state["finding"])) is not None
                saved_evaluation = await db.get(DueDiligenceEvaluation, UUID(state["evaluation"]))
                assert saved_evaluation and saved_evaluation.inputs == {"synthetic": True}
                policy = await db.scalar(
                    select(PolicyVersion).where(
                        PolicyVersion.policy_type == "PRIVACY_NOTICE",
                        PolicyVersion.version == "2026-11-12-m3",
                    )
                )
                assert (
                    policy
                    and hashlib.sha256(policy.text.encode()).hexdigest() == state["policy_hash"]
                )
                ack = await db.scalar(
                    select(UserPolicyAcknowledgement).where(
                        UserPolicyAcknowledgement.user_id == UUID(state["account"])
                    )
                )
                assert ack and ack.policy_version_id == policy.id
                current = await db.scalar(
                    select(PolicyVersion).where(
                        PolicyVersion.policy_type == "PRIVACY_NOTICE",
                        PolicyVersion.current.is_(True),
                    )
                )
                assert current and current.version == (
                    "2026-11-12-m3" if mode == "verify-m3" else "2026-11-12-m4"
                )
                print(
                    "M3 bytes, analysis, evidence, rule result, evaluation "
                    "and old notice/ack survive"
                )
            elif mode == "guard":
                for variant in ["evaluation", "manual-classification"]:
                    if variant == "evaluation":
                        blocker = CoOwnershipEvaluation(
                            workspace_id=wid,
                            evaluation_date=date(2026, 11, 12),
                            input_hash="e" * 64,
                            identity_revision=None,
                            result={},
                            inputs={},
                        )
                        db.add(blocker)
                    else:
                        await db.execute(
                            update(DocumentAnalysis)
                            .where(DocumentAnalysis.id == aid)
                            .values(manual_classification=AnalysisKind.AGM_MINUTES)
                        )
                    await db.commit()
                    process = await asyncio.create_subprocess_exec(
                        sys.executable,
                        "-m",
                        "alembic",
                        "downgrade",
                        "192e0442ffc8",
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )
                    _, error = await process.communicate()
                    assert process.returncode != 0 and b"Remove M4 dossier data" in error
                    assert (
                        await db.scalar(text("SELECT version_num FROM alembic_version"))
                        == "d64802d3610f"
                    )
                    if variant == "evaluation":
                        assert await db.get(CoOwnershipEvaluation, blocker.id) is not None
                        await db.execute(
                            delete(CoOwnershipEvaluation).where(
                                CoOwnershipEvaluation.workspace_id == wid
                            )
                        )
                    else:
                        await db.execute(
                            update(DocumentAnalysis)
                            .where(DocumentAnalysis.id == aid)
                            .values(manual_classification=None)
                        )
                    await db.commit()
                print("Evaluation and manual-kind-only M4 state both refuse downgrade atomically")
            elif mode == "cleanup":
                await db.execute(delete(Account).where(Account.id == UUID(state["account"])))
                await db.commit()
                storage.delete(state["source_key"])
                storage.delete(state["artifact_key"])
                print("Removed only the synthetic M4 migration sentinel and its private bytes")
            else:
                raise ValueError("Choose seed, verify, verify-m3, guard or cleanup")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run(sys.argv[1]))
