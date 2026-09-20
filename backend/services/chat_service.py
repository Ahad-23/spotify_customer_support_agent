"""Chat orchestration — wraps run_support_agent without modifying agent code."""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from backend.models import (
    ChatMessage,
    ChatSession,
    HitlTicket,
    MessageRole,
    SessionStatus,
    TicketStatus,
)
from backend.schemas import MessageResponse
from backend.services.websocket_manager import ws_manager
from src.agent.graph import run_support_agent


def _message_to_response(msg: ChatMessage) -> MessageResponse:
    return MessageResponse.from_orm_message(msg)


def create_session(db: Session, customer_name: str | None = None) -> ChatSession:
    session = ChatSession(customer_name=customer_name)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def get_session(db: Session, session_id: str) -> ChatSession | None:
    return db.get(ChatSession, session_id)


def _save_message(
    db: Session,
    session: ChatSession,
    role: MessageRole,
    content: str,
    metadata: dict | None = None,
) -> ChatMessage:
    msg = ChatMessage(
        session_id=session.id,
        role=role,
        content=content,
        metadata_=metadata,
    )
    db.add(msg)
    session.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(msg)
    return msg


async def handle_customer_message(
    db: Session,
    session: ChatSession,
    content: str,
) -> MessageResponse:
    customer_msg = _save_message(db, session, MessageRole.CUSTOMER, content)
    await ws_manager.send_to_session(
        session.id,
        {"type": "message", "message": _message_to_response(customer_msg).model_dump(mode="json")},
    )

    if session.status == SessionStatus.HUMAN_ACTIVE:
        await ws_manager.broadcast_to_agents(
            {
                "type": "customer_message",
                "session_id": session.id,
                "message": _message_to_response(customer_msg).model_dump(mode="json"),
            }
        )
        return _message_to_response(customer_msg)

    if session.status in (SessionStatus.HITL_PENDING, SessionStatus.CLOSED):
        system_text = (
            "A support specialist will respond shortly. Please hold on."
            if session.status == SessionStatus.HITL_PENDING
            else "This conversation has been closed."
        )
        sys_msg = _save_message(db, session, MessageRole.SYSTEM, system_text)
        await ws_manager.send_to_session(
            session.id,
            {"type": "message", "message": _message_to_response(sys_msg).model_dump(mode="json")},
        )
        return _message_to_response(customer_msg)

    state = run_support_agent(content, history=session.agent_history or [])
    session.agent_history = state.messages

    agent_metadata = {
        "intent": state.intent,
        "device_info": state.device_info,
        "confidence_score": state.confidence_score,
        "sentiment": state.sentiment,
        "frustration_score": state.frustration_score,
        "requires_escalation": state.requires_escalation,
        "is_hitl": state.is_hitl,
    }

    agent_msg = _save_message(
        db,
        session,
        MessageRole.AGENT,
        state.final_response,
        metadata=agent_metadata,
    )

    await ws_manager.send_to_session(
        session.id,
        {"type": "message", "message": _message_to_response(agent_msg).model_dump(mode="json")},
    )

    if state.is_hitl and state.handoff_ticket:
        session.status = SessionStatus.HITL_PENDING
        ticket = HitlTicket(
            session_id=session.id,
            ticket_id=state.handoff_ticket["ticket_id"],
            priority=state.handoff_ticket.get("priority", "Standard"),
            handoff_data=state.handoff_ticket,
        )
        db.add(ticket)

        hold_msg = _save_message(
            db,
            session,
            MessageRole.SYSTEM,
            "Connecting you with a support specialist. You'll be notified when someone joins.",
        )
        db.commit()
        db.refresh(ticket)

        await ws_manager.send_to_session(
            session.id,
            {
                "type": "hitl_pending",
                "message": _message_to_response(hold_msg).model_dump(mode="json"),
                "ticket": {
                    "ticket_id": ticket.ticket_id,
                    "priority": ticket.priority,
                },
            },
        )
        await ws_manager.broadcast_to_agents(
            {
                "type": "hitl_new",
                "ticket": {
                    "id": ticket.id,
                    "session_id": session.id,
                    "ticket_id": ticket.ticket_id,
                    "priority": ticket.priority,
                    "status": ticket.status.value,
                    "handoff_data": ticket.handoff_data,
                    "customer_name": session.customer_name,
                    "created_at": ticket.created_at.isoformat(),
                },
            }
        )
    else:
        db.commit()

    return _message_to_response(agent_msg)


async def handle_agent_message(
    db: Session,
    session: ChatSession,
    agent_name: str,
    content: str,
) -> MessageResponse:
    msg = _save_message(db, session, MessageRole.HUMAN_AGENT, content, metadata={"agent_name": agent_name})

    if session.agent_history is None:
        session.agent_history = []
    session.agent_history.append({"role": "agent", "content": content})
    db.commit()
    db.refresh(msg)

    response = _message_to_response(msg)
    await ws_manager.send_to_session(
        session.id,
        {"type": "message", "message": response.model_dump(mode="json")},
    )
    return response


async def claim_ticket(db: Session, ticket: HitlTicket, agent_name: str) -> HitlTicket:
    ticket.status = TicketStatus.CLAIMED
    ticket.claimed_by = agent_name
    ticket.claimed_at = datetime.now(timezone.utc)
    ticket.session.status = SessionStatus.HUMAN_ACTIVE

    join_msg = _save_message(
        db,
        ticket.session,
        MessageRole.SYSTEM,
        f"{agent_name} has joined the conversation.",
    )
    db.commit()
    db.refresh(ticket)

    await ws_manager.send_to_session(
        ticket.session_id,
        {
            "type": "agent_joined",
            "agent_name": agent_name,
            "message": _message_to_response(join_msg).model_dump(mode="json"),
        },
    )
    await ws_manager.broadcast_to_agents(
        {
            "type": "hitl_claimed",
            "ticket_id": ticket.id,
            "session_id": ticket.session_id,
            "claimed_by": agent_name,
        }
    )
    return ticket


async def resolve_ticket(db: Session, ticket: HitlTicket) -> HitlTicket:
    ticket.status = TicketStatus.RESOLVED
    ticket.resolved_at = datetime.now(timezone.utc)
    ticket.session.status = SessionStatus.CLOSED

    close_msg = _save_message(
        db,
        ticket.session,
        MessageRole.SYSTEM,
        "This conversation has been resolved. Thank you for contacting support.",
    )
    db.commit()
    db.refresh(ticket)

    await ws_manager.send_to_session(
        ticket.session_id,
        {
            "type": "session_closed",
            "message": _message_to_response(close_msg).model_dump(mode="json"),
        },
    )
    await ws_manager.broadcast_to_agents(
        {"type": "hitl_resolved", "ticket_id": ticket.id, "session_id": ticket.session_id}
    )
    return ticket
