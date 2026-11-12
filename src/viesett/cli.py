import argparse
import asyncio
import json

from viesett.core.config import Settings
from viesett.db.session import create_engine, session_factory
from viesett.integrations.smoke import live_source_smoke
from viesett.services.auth import provision_account
from viesett.services.deletion import purge_archived, purge_objects
from viesett.storage.private import LocalPrivateStorage


async def run(command: str, settings: Settings) -> None:
    if command == "live-sources":
        print(json.dumps(await live_source_smoke(settings)))
        return
    engine = create_engine(settings)
    try:
        async with session_factory(engine)() as db:
            if command == "create-account":
                if settings.environment == "production":
                    raise RuntimeError("Development account provisioning is disabled in production")
                account, token = await provision_account(db, settings.token_lifetime_hours)
                # Explicit, one-time credential issuance to the terminal, never application logs.
                print(json.dumps({"account_id": str(account.id), "token": token}))
            else:
                storage = LocalPrivateStorage(settings.storage_root)
                archived = await purge_archived(db, storage, settings.archived_retention_days)
                objects = await purge_objects(db, storage)
                print(
                    json.dumps({"archived_workspaces_purged": archived, "objects_purged": objects})
                )
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(prog="viesett")
    parser.add_argument("command", choices=["create-account", "purge", "live-sources"])
    args = parser.parse_args()
    asyncio.run(run(args.command, Settings()))


if __name__ == "__main__":
    main()
