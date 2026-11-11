from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from viesett.db.models import PolicyVersion, UserPolicyAcknowledgement
from viesett.domain.schemas import AcknowledgementOut
from viesett.domain.types import PolicyType


async def acknowledge(db: AsyncSession, user_id: UUID, version_id: UUID) -> None:
    policy = await db.get(PolicyVersion, version_id)
    if policy is None or not policy.current:
        raise HTTPException(409, "A current policy version is required")
    await db.execute(
        insert(UserPolicyAcknowledgement)
        .values(
            user_id=user_id,
            policy_version_id=version_id,
        )
        .on_conflict_do_nothing(index_elements=["user_id", "policy_version_id"])
    )
    await db.commit()


async def require_upload_attestation(db: AsyncSession, user_id: UUID) -> None:
    acknowledgement = await db.scalar(
        select(UserPolicyAcknowledgement.id)
        .join(PolicyVersion)
        .where(
            UserPolicyAcknowledgement.user_id == user_id,
            PolicyVersion.policy_type == PolicyType.UPLOAD_ATTESTATION,
            PolicyVersion.current.is_(True),
        )
    )
    if acknowledgement is None:
        raise HTTPException(409, "Current upload attestation required")


async def acknowledgements(db: AsyncSession, user_id: UUID) -> list[AcknowledgementOut]:
    rows = (
        await db.execute(
            select(UserPolicyAcknowledgement, PolicyVersion)
            .join(PolicyVersion)
            .where(UserPolicyAcknowledgement.user_id == user_id)
        )
    ).all()
    return [
        AcknowledgementOut(
            policy_version_id=policy.id,
            policy_type=policy.policy_type,
            policy_version=policy.version,
            acknowledged_at=ack.acknowledged_at,
        )
        for ack, policy in rows
    ]
