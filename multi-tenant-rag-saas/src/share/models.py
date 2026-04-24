"""Shared SQLAlchemy models used across app / admin / ws services.

Only the tenant + user shape is shown, just enough to ground the
RBAC middleware. The full schema (conversations, messages,
documents, chunks, token_usage, billing_accounts) lives in the
private repo.

TODO: see private repo for full impl.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

EffectiveRole = Literal["super_admin", "tenant_admin", "user"]
BillingModel = Literal["pay_per_use", "prepaid", "monthly_limit"]


class Base(DeclarativeBase):
    pass


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    billing_model: Mapped[BillingModel] = mapped_column(
        String(32), nullable=False, default="pay_per_use"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    users: Mapped[list["User"]] = relationship(back_populates="tenant")


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=True
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    is_system_user: Mapped[bool] = mapped_column(Boolean, default=False)
    effective_role: Mapped[EffectiveRole] = mapped_column(
        String(32), nullable=False, default="user"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    tenant: Mapped[Tenant | None] = relationship(back_populates="users")

    @property
    def is_super_admin(self) -> bool:
        return self.is_system_user and self.effective_role == "super_admin"


# TODO: see private repo for:
#   - Conversation, Message (chat history)
#   - Document, Chunk (RAG ingest)
#   - TokenUsage, BillingAccount (accounting + billing)
