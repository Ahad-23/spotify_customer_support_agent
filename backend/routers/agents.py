"""REST routes for human support agent dashboard."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from backend.database import get_db
from backend.models import ChatSession, HitlTicket, TicketStatus
from backend.schemas import (
    AgentMessageCreate,
    ClaimTicketRequest,
    HitlTicketResponse,
    MessageResponse,
    SessionDetailResponse,
)
from backend.services import chat_service

router = APIRouter(prefix="/api/agents", tags=["agents"])


def _ticket_response(ticket: HitlTicket) -> HitlTicketResponse:
    last_msg = None
    if ticket.session and ticket.session.messages:
        last_msg = ticket.session.messages[-1].content
    return HitlTicketResponse(
        id=ticket.id,
        session_id=ticket.session_id,
        ticket_id=ticket.ticket_id,
        priority=ticket.priority,
        status=ticket.status,
        handoff_data=ticket.handoff_data,
        claimed_by=ticket.claimed_by,
        claimed_at=ticket.claimed_at,
        created_at=ticket.created_at,
        customer_name=ticket.session.customer_name if ticket.session else None,
        last_message=last_msg,
    )


@router.get("/tickets", response_model=list[HitlTicketResponse])
def list_tickets(status: str | None = None, db: Session = Depends(get_db)):
    query = (
        db.query(HitlTicket)
        .options(joinedload(HitlTicket.session).joinedload(ChatSession.messages))
        .order_by(HitlTicket.created_at.desc())
    )
    if status:
        try:
            ticket_status = TicketStatus(status)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid status") from exc
        query = query.filter(HitlTicket.status == ticket_status)
    tickets = query.all()
    return [_ticket_response(t) for t in tickets]


@router.post("/tickets/{ticket_id}/claim", response_model=HitlTicketResponse)
async def claim_ticket(ticket_id: str, body: ClaimTicketRequest, db: Session = Depends(get_db)):
    ticket = (
        db.query(HitlTicket)
        .options(joinedload(HitlTicket.session))
        .filter(HitlTicket.id == ticket_id)
        .first()
    )
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if ticket.status != TicketStatus.PENDING:
        raise HTTPException(status_code=409, detail="Ticket already claimed or resolved")

    ticket = await chat_service.claim_ticket(db, ticket, body.agent_name.strip())
    return _ticket_response(ticket)


@router.post("/tickets/{ticket_id}/resolve", response_model=HitlTicketResponse)
async def resolve_ticket(ticket_id: str, db: Session = Depends(get_db)):
    ticket = (
        db.query(HitlTicket)
        .options(joinedload(HitlTicket.session))
        .filter(HitlTicket.id == ticket_id)
        .first()
    )
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if ticket.status == TicketStatus.RESOLVED:
        raise HTTPException(status_code=409, detail="Ticket already resolved")

    ticket = await chat_service.resolve_ticket(db, ticket)
    return _ticket_response(ticket)


@router.get("/sessions/{session_id}", response_model=SessionDetailResponse)
def get_agent_session_view(session_id: str, db: Session = Depends(get_db)):
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


@router.post("/sessions/{session_id}/messages", response_model=MessageResponse)
async def send_agent_message(
    session_id: str,
    body: AgentMessageCreate,
    agent_name: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
):
    session = chat_service.get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if not agent_name.strip():
        raise HTTPException(status_code=400, detail="agent_name query param required")

    return await chat_service.handle_agent_message(
        db, session, agent_name.strip(), body.content.strip()
    )
