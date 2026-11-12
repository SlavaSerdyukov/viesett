"""CI migration sentinel: only run against a dedicated disposable test database."""

import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy import text

from viesett.core.config import Settings
from viesett.db.session import create_engine

STATE = Path(".local/migration-sentinel.json")


async def check(mode: str) -> None:
    engine = create_engine(Settings())
    try:
        async with engine.begin() as connection:
            if mode == "seed":
                account, workspace = str(uuid4()), str(uuid4())
                now = datetime.now(UTC)
                await connection.execute(
                    text("INSERT INTO accounts (id, created_at) VALUES (:id, :now)"),
                    {"id": account, "now": now},
                )
                await connection.execute(
                    text(
                        "INSERT INTO property_workspaces "
                        "(id, owner_user_id, status, canonical_address, region, "
                        "created_at, updated_at) "
                        "VALUES (:id, :owner, 'ACTIVE', 'Synthetic migration sentinel', "
                        "'FLANDERS', :now, :now)"
                    ),
                    {"id": workspace, "owner": account, "now": now},
                )
                for kind in ["PRIVACY_NOTICE", "UPLOAD_ATTESTATION"]:
                    await connection.execute(
                        text(
                            "INSERT INTO user_policy_acknowledgements "
                            "(id, user_id, policy_version_id, acknowledged_at, created_at) "
                            "SELECT :id, :user, id, :now, :now FROM policy_versions "
                            "WHERE policy_type = :kind AND version = '2026-11-11'"
                        ),
                        {"id": str(uuid4()), "user": account, "now": now, "kind": kind},
                    )
                await asyncio.to_thread(STATE.parent.mkdir, parents=True, exist_ok=True)
                await asyncio.to_thread(
                    STATE.write_text, json.dumps({"account": account, "workspace": workspace})
                )
                print("Seeded synthetic Milestone 1 account, workspace and acknowledgements")
            elif mode == "verify":
                state = json.loads(await asyncio.to_thread(STATE.read_text))
                address = await connection.scalar(
                    text("SELECT canonical_address FROM property_workspaces WHERE id = :id"),
                    {"id": state["workspace"]},
                )
                assert address == "Synthetic migration sentinel"
                acknowledgements = await connection.scalar(
                    text(
                        "SELECT count(*) FROM user_policy_acknowledgements a "
                        "JOIN policy_versions p ON p.id = a.policy_version_id "
                        "WHERE a.user_id = :id AND p.version = '2026-11-11'"
                    ),
                    {"id": state["account"]},
                )
                assert acknowledgements == 2
                versions = (
                    await connection.execute(
                        text(
                            "SELECT policy_type, version FROM policy_versions WHERE current = true"
                        )
                    )
                ).all()
                assert ("PRIVACY_NOTICE", "2026-11-11-m2") in versions
                assert ("UPLOAD_ATTESTATION", "2026-11-11") in versions
                checks = await connection.scalar(
                    text(
                        "SELECT count(*) FROM pg_constraint "
                        "WHERE conrelid = 'evidence_items'::regclass "
                        "AND conname IN ('ck_evidence_items_provider_authority', "
                        "'ck_evidence_items_official_provenance_complete')"
                    )
                )
                assert checks == 2
                await connection.execute(
                    text("DELETE FROM accounts WHERE id = :id"), {"id": state["account"]}
                )
                print(
                    "M1 data and acknowledgement history preserved; M2 checks and notice verified"
                )
            else:
                raise ValueError("Choose seed or verify")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(check(sys.argv[1]))
