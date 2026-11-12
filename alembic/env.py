import asyncio

from sqlalchemy import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context
from viesett.core.config import Settings
from viesett.db import coownership_models as coownership_models
from viesett.db import intelligence_models as intelligence_models
from viesett.db import product_models as product_models
from viesett.db import property_models as property_models
from viesett.db.models import Base

config = context.config
target_metadata = Base.metadata


def migrate(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def online() -> None:
    settings = Settings()
    engine = create_async_engine(settings.database_url.get_secret_value(), hide_parameters=True)
    async with engine.connect() as connection:
        await connection.run_sync(migrate)
    await engine.dispose()


if context.is_offline_mode():
    context.configure(
        url=Settings().database_url.get_secret_value(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    asyncio.run(online())
