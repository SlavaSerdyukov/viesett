"""M5 -> M6 preservation/rollback sentinel. Dedicated disposable test DB only."""

import asyncio
import hashlib
import json
import secrets
import sys
from datetime import timedelta
from pathlib import Path
from uuid import UUID

from sqlalchemy import delete, select, text

from viesett.core.config import Settings
from viesett.db.beta_models import BrowserSession
from viesett.db.models import (
    Account,
    ApiToken,
    EvidenceItem,
    PolicyVersion,
    PropertyWorkspace,
    UserPolicyAcknowledgement,
    utcnow,
)
from viesett.db.session import create_engine, session_factory
from viesett.domain.types import Authority, PolicyType, SourceType
from viesett.services.auth import provision_account

STATE = Path(".local/m6-migration-sentinel.json")


async def rejected_downgrade() -> None:
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "alembic",
        "downgrade",
        "f51e9bf1a005",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, error = await process.communicate()
    assert process.returncode != 0 and b"Remove private browser sessions" in error


async def run(mode: str) -> None:
    engine = create_engine(Settings())
    try:
        async with session_factory(engine)() as db:
            if mode == "seed":
                assert (
                    await db.scalar(text("SELECT version_num FROM alembic_version"))
                    == "f51e9bf1a005"
                )
                account, _ = await provision_account(db)
                token = await db.scalar(select(ApiToken).where(ApiToken.user_id == account.id))
                workspace = PropertyWorkspace(
                    owner_user_id=account.id, canonical_address="Synthetic M5 preservation"
                )
                db.add(workspace)
                await db.flush()
                evidence = EvidenceItem(
                    workspace_id=workspace.id,
                    key="transaction.synthetic_sentinel",
                    typed_value={"kind": "boolean", "value": True},
                    source_type=SourceType.MANUAL,
                    authority=Authority.INFERRED,
                    source_locator={"section": "Synthetic M5 sentinel"},
                )
                notice = await db.scalar(
                    select(PolicyVersion).where(
                        PolicyVersion.policy_type == PolicyType.PRIVACY_NOTICE,
                        PolicyVersion.current.is_(True),
                    )
                )
                assert notice and token
                db.add_all(
                    [
                        evidence,
                        UserPolicyAcknowledgement(user_id=account.id, policy_version_id=notice.id),
                    ]
                )
                await db.commit()
                state = {
                    "account": str(account.id),
                    "workspace": str(workspace.id),
                    "evidence": str(evidence.id),
                    "token": str(token.id),
                    "token_hash": token.token_hash,
                    "notice": str(notice.id),
                    "notice_hash": hashlib.sha256(notice.text.encode()).hexdigest(),
                }
                await asyncio.to_thread(STATE.parent.mkdir, parents=True, exist_ok=True)
                await asyncio.to_thread(STATE.write_text, json.dumps(state))
                print(
                    "Seeded synthetic M5 owner, token authority, evidence "
                    "and notice acknowledgement"
                )
                return
            state = json.loads(await asyncio.to_thread(STATE.read_text))
            wid, aid = UUID(state["workspace"]), UUID(state["account"])
            if mode == "verify":
                saved_workspace = await db.get(PropertyWorkspace, wid)
                saved_evidence = await db.get(EvidenceItem, UUID(state["evidence"]))
                token = await db.get(ApiToken, UUID(state["token"]))
                notice = await db.get(PolicyVersion, UUID(state["notice"]))
                ack = await db.scalar(
                    select(UserPolicyAcknowledgement).where(
                        UserPolicyAcknowledgement.user_id == aid,
                        UserPolicyAcknowledgement.policy_version_id == UUID(state["notice"]),
                    )
                )
                assert (
                    saved_workspace
                    and saved_workspace.owner_user_id == aid
                    and saved_workspace.canonical_address == "Synthetic M5 preservation"
                )
                assert (
                    saved_evidence
                    and saved_evidence.authority == Authority.INFERRED
                    and saved_evidence.typed_value == {"kind": "boolean", "value": True}
                )
                assert token and token.token_hash == state["token_hash"]
                assert (
                    notice
                    and hashlib.sha256(notice.text.encode()).hexdigest() == state["notice_hash"]
                    and ack
                )
                print(
                    "M5 owner, bearer authority, evidence and original notice/ack "
                    "survive upgrade/downgrade"
                )
            elif mode == "guard":
                row = BrowserSession(
                    user_id=aid,
                    api_token_id=UUID(state["token"]),
                    secret_hash=hashlib.sha256(secrets.token_bytes(48)).hexdigest(),
                    csrf_token=secrets.token_urlsafe(32),
                    expires_at=utcnow() + timedelta(hours=1),
                )
                db.add(row)
                await db.commit()
                await rejected_downgrade()
                assert (
                    await db.scalar(text("SELECT version_num FROM alembic_version"))
                    == "c82e16a7b603"
                )
                assert await db.get(BrowserSession, row.id)
                await db.delete(row)
                context = EvidenceItem(
                    workspace_id=wid,
                    key="transaction.authentic_deed_date",
                    typed_value={"kind": "date", "value": "2026-11-01"},
                    source_type=SourceType.MANUAL,
                    authority=Authority.UNVERIFIED,
                    source_locator={"method": "user-transaction-context:1.0.0"},
                )
                db.add(context)
                await db.commit()
                await rejected_downgrade()
                assert (
                    await db.scalar(text("SELECT version_num FROM alembic_version"))
                    == "c82e16a7b603"
                )
                assert await db.get(EvidenceItem, context.id)
                await db.delete(context)
                await db.commit()
                print(
                    "Session and unverified context each block downgrade atomically; "
                    "synthetic guard rows removed"
                )
            elif mode == "cleanup":
                await db.execute(delete(Account).where(Account.id == aid))
                await db.commit()
                print("Only the task-owned synthetic M6 sentinel account removed")
            else:
                raise ValueError("Choose seed, verify, guard or cleanup")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run(sys.argv[1]))
