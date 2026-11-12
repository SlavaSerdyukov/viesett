"""M4 -> M5 preservation and demo-label rollback guard. Disposable test DB only."""

import asyncio
import hashlib
import json
import sys
from datetime import date
from pathlib import Path
from uuid import UUID

from sqlalchemy import delete, text

from viesett.coownership.context import CrossDocumentContext
from viesett.coownership.engine import evaluate
from viesett.core.config import Settings
from viesett.db.coownership_models import CoOwnershipEvaluation
from viesett.db.models import Account, PropertyWorkspace
from viesett.db.product_models import DemoWorkspace
from viesett.db.session import create_engine, session_factory
from viesett.domain.property import FloodResult, PropertySnapshot

STATE = Path(".local/m5-migration-sentinel.json")


def fingerprint(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


async def run(mode: str) -> None:
    engine = create_engine(Settings())
    try:
        async with session_factory(engine)() as db:
            if mode == "seed":
                assert (
                    await db.scalar(text("SELECT version_num FROM alembic_version"))
                    == "d64802d3610f"
                )
                account = Account()
                db.add(account)
                await db.flush()
                workspace = PropertyWorkspace(
                    owner_user_id=account.id, canonical_address="Synthetic M4 preservation"
                )
                db.add(workspace)
                await db.flush()
                property = PropertySnapshot(
                    workspace_id=workspace.id,
                    resolution_status=None,
                    latest_input_address_query=None,
                    snapshot_input_address_query=None,
                    property_key=None,
                    identity_revision=None,
                    last_successful_retrieval=None,
                    stale=True,
                    flood=FloodResult(status="NOT_APPLICABLE"),
                )
                result = evaluate(
                    CrossDocumentContext(workspace.id, date(2026, 11, 12), property, ())
                ).model_dump(mode="json")
                row = CoOwnershipEvaluation(
                    workspace_id=workspace.id,
                    evaluation_date=date(2026, 11, 12),
                    input_hash="f" * 64,
                    identity_revision=None,
                    result=result,
                    inputs={"synthetic_m4": True},
                )
                db.add(row)
                await db.commit()
                await asyncio.to_thread(STATE.parent.mkdir, parents=True, exist_ok=True)
                await asyncio.to_thread(
                    STATE.write_text,
                    json.dumps(
                        {
                            "account": str(account.id),
                            "workspace": str(workspace.id),
                            "evaluation": str(row.id),
                            "fingerprint": fingerprint(result),
                        }
                    ),
                )
                print("Seeded valid M4 typed evaluation and private workspace")
                return
            state = json.loads(await asyncio.to_thread(STATE.read_text))
            wid = UUID(state["workspace"])
            if mode == "verify":
                saved_row = await db.get(CoOwnershipEvaluation, UUID(state["evaluation"]))
                saved_workspace = await db.get(PropertyWorkspace, wid)
                assert saved_row and fingerprint(saved_row.result) == state["fingerprint"]
                assert saved_row.inputs == {"synthetic_m4": True}
                assert (
                    saved_workspace
                    and saved_workspace.canonical_address == "Synthetic M4 preservation"
                )
                print(
                    "M4 typed result, normalized inputs, owner and property "
                    "survive M5 upgrade/downgrade"
                )
            elif mode == "guard":
                db.add(DemoWorkspace(workspace_id=wid))
                await db.commit()
                process = await asyncio.create_subprocess_exec(
                    sys.executable,
                    "-m",
                    "alembic",
                    "downgrade",
                    "d64802d3610f",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                _, error = await process.communicate()
                assert process.returncode != 0 and b"Delete demo workspaces" in error
                assert (
                    await db.scalar(text("SELECT version_num FROM alembic_version"))
                    == "f51e9bf1a005"
                )
                assert await db.get(DemoWorkspace, wid) is not None
                await db.execute(delete(DemoWorkspace).where(DemoWorkspace.workspace_id == wid))
                await db.commit()
                print(
                    "Nonempty demo label blocks downgrade atomically; "
                    "label cannot silently disappear"
                )
            elif mode == "cleanup":
                await db.execute(delete(Account).where(Account.id == UUID(state["account"])))
                await db.commit()
                print("Synthetic M5 migration sentinel removed")
            else:
                raise ValueError("Choose seed, verify, guard or cleanup")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run(sys.argv[1]))
