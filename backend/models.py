"""SQLAlchemy models for chat sessions, messages, and HITL tickets."""

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


class SessionStatus(str, enum.Enum):
    ACTIVE_AI = "active_ai"
    HITL_PENDING = "hitl_pending"
    HUMAN_ACTIVE = "human_active"
    CLOSED = "closed"


class TicketStatus(str, enum.Enum):
    PENDING = "pending"
    CLAIMED = "claimed"
    RESOLVED = "resolved"


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    customer_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[SessionStatus] = mapped_column(
        Enum(SessionStatus), default=SessionStatus.ACTIVE_AI
    )
    agent_history: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="session",
        order_by="ChatMessage.created_at",
        cascade="all, delete-orphan",
    )
    hitl_ticket: Mapped["HitlTicket | None"] = relationship(
        back_populates="session",
        uselist=False,
        cascade="all, delete-orphan",
    )


class MessageRole(str, enum.Enum):
    CUSTOMER = "customer"
    AGENT = "agent"
    HUMAN_AGENT = "human_agent"
    SYSTEM = "system"


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("chat_sessions.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[MessageRole] = mapped_column(Enum(MessageRole))
    content: Mapped[str] = mapped_column(Text)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    session: Mapped["ChatSession"] = relationship(back_populates="messages")


class HitlTicket(Base):
    __tablename__ = "hitl_tickets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("chat_sessions.id", ondelete="CASCADE"), unique=True, index=True
    )
    ticket_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    priority: Mapped[str] = mapped_column(String(32), default="Standard")
    status: Mapped[TicketStatus] = mapped_column(Enum(TicketStatus), default=TicketStatus.PENDING)
    handoff_data: Mapped[dict] = mapped_column(JSON, default=dict)
    claimed_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    session: Mapped["ChatSession"] = relationship(back_populates="hitl_ticket")
