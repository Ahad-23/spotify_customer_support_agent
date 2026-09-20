"""REST routes for customer chat sessions."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from backend.database import get_db
from backend.models import ChatSession, HitlTicket, TicketStatus
from backend.schemas import (
    HitlTicketResponse,
    MessageCreate,
    MessageResponse,
    SessionCreate,
    SessionDetailResponse,
    SessionResponse,
)
from backend.services import chat_service

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.post("", response_model=SessionResponse)
def create_session(body: SessionCreate, db: Session = Depends(get_db)):
    session = chat_service.create_session(db, customer_name=body.customer_name)
    return session


@router.get("/{session_id}", response_model=SessionDetailResponse)
def get_session(session_id: str, db: Session = Depends(get_db)):
    session = (
        db.query(ChatSession)
        .options(joinedload(ChatSession.messages), joinedload(ChatSession.hitl_ticket))
        .filter(ChatSession.id == session_id)
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    ticket = None
    if session.hitl_ticket:
        ticket = HitlTicketResponse.model_validate(session.hitl_ticket)

    return SessionDetailResponse(
        id=session.id,
        customer_name=session.customer_name,
        status=session.status,
        created_at=session.created_at,
        updated_at=session.updated_at,
        messages=[MessageResponse.from_orm_message(m) for m in session.messages],
        hitl_ticket=ticket,
    )


@router.post("/{session_id}/messages", response_model=MessageResponse)
async def send_message(session_id: str, body: MessageCreate, db: Session = Depends(get_db)):
    session = chat_service.get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    result = await chat_service.handle_customer_message(db, session, body.content.strip())
    return result
