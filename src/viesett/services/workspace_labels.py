from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from viesett.db.models import PropertyWorkspace
from viesett.db.product_models import DemoWorkspace
from viesett.domain.schemas import WorkspaceOut


async def label_workspaces(
    db: AsyncSession, rows: Sequence[PropertyWorkspace]
) -> list[WorkspaceOut]:
    ids = [row.id for row in rows]
    demo_ids = set(
        (
            await db.scalars(
                select(DemoWorkspace.workspace_id).where(DemoWorkspace.workspace_id.in_(ids))
            )
        ).all()
    )
    return [
        WorkspaceOut.model_validate(row).model_copy(update={"is_demo": row.id in demo_ids})
        for row in rows
    ]
