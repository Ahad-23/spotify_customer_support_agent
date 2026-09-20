"""Pydantic schemas for API request/response bodies."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from backend.models import MessageRole, SessionStatus, TicketStatus


class SessionCreate(BaseModel):
    customer_name: str | None = None


class SessionResponse(BaseModel):
    id: str
    customer_name: str | None
    status: SessionStatus
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


class MessageResponse(BaseModel):
    id: str
    session_id: str
    role: MessageRole
    content: str
    metadata: dict[str, Any] | None = None
    created_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_message(cls, msg) -> "MessageResponse":
        return cls(
            id=msg.id,
            session_id=msg.session_id,
            role=msg.role,
            content=msg.content,
            metadata=msg.metadata_,
            created_at=msg.created_at,
        )


class HitlTicketResponse(BaseModel):
    id: str
    session_id: str
    ticket_id: str
    priority: str
    status: TicketStatus
    handoff_data: dict[str, Any]
    claimed_by: str | None
    claimed_at: datetime | None
    created_at: datetime
    customer_name: str | None = None
    last_message: str | None = None

    model_config = {"from_attributes": True}


class ClaimTicketRequest(BaseModel):
    agent_name: str = Field(min_length=1, max_length=120)


class AgentMessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


class SessionDetailResponse(SessionResponse):
    messages: list[MessageResponse]
    hitl_ticket: HitlTicketResponse | None = None
