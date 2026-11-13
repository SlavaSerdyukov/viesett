from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, ForeignKeyConstraint, String
from sqlalchemy.orm import Mapped, mapped_column

from viesett.db.models import Base, Identity


class BrowserSession(Identity, Base):
    __tablename__ = "browser_sessions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["api_token_id", "user_id"],
            ["api_tokens.id", "api_tokens.user_id"],
            ondelete="CASCADE",
        ),
    )
    user_id: Mapped[UUID] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    api_token_id: Mapped[UUID] = mapped_column(index=True)
    secret_hash: Mapped[str] = mapped_column(String(64), unique=True)
    # Synchronizer token is not an authentication credential. Never exported.
    csrf_token: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
