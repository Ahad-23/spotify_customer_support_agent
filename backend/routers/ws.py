"""WebSocket endpoints for real-time customer and agent updates."""

import json

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from backend.database import SessionLocal
from backend.services import chat_service
from backend.services.websocket_manager import ws_manager

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/sessions/{session_id}")
async def customer_websocket(session_id: str, websocket: WebSocket):
    db = SessionLocal()
    try:
        session = chat_service.get_session(db, session_id)
        if not session:
            await websocket.close(code=4004)
            return

        await ws_manager.connect_customer(session_id, websocket)
        try:
            while True:
                raw = await websocket.receive_text()
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                if data.get("type") == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
                    continue

                content = (data.get("content") or "").strip()
                if not content:
                    continue

                await chat_service.handle_customer_message(db, session, content)
                db.refresh(session)
        except WebSocketDisconnect:
            ws_manager.disconnect_customer(session_id, websocket)
    finally:
        db.close()


@router.websocket("/ws/agents")
async def agent_websocket(websocket: WebSocket):
    await ws_manager.connect_agent(websocket)
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue

            if data.get("type") == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        ws_manager.disconnect_agent(websocket)
