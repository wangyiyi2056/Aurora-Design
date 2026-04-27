from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from chatbi_serve.chat.schema import (
    ChatRequest,
    ChatResponse,
    SessionCreateResponse,
    SessionListResponse,
    SessionLoadResponse,
    SessionMetaResponse,
)
from chatbi_serve.chat.service import ChatService

router = APIRouter(prefix="/chat", tags=["chat"])


def get_chat_service(request: Request) -> ChatService:
    return request.app.state.chat_service


@router.post("/completions", response_model=ChatResponse)
async def chat_completions(
    req: ChatRequest, service: ChatService = Depends(get_chat_service)
) -> ChatResponse | StreamingResponse:
    if req.stream:
        return StreamingResponse(
            service.chat_stream(req, session_id=req.session_id),
            media_type="text/event-stream",
        )
    return await service.chat(req, session_id=req.session_id)


# --- Session Management Endpoints ---


@router.post("/sessions", response_model=SessionCreateResponse)
async def create_session(
    service: ChatService = Depends(get_chat_service),
) -> SessionCreateResponse:
    session = service.start_new_session()
    return SessionCreateResponse(session_id=session.id)


@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions(
    service: ChatService = Depends(get_chat_service),
) -> SessionListResponse:
    sessions = service.list_sessions()
    items: list[SessionMetaResponse] = [
        SessionMetaResponse(
            id=s["id"],
            title=s.get("title", "New Chat"),
            created_at=s.get("created_at", 0),
            updated_at=s.get("updated_at", 0),
            message_count=s.get("message_count", 0),
        )
        for s in sessions
        if s.get("message_count", 0) > 0
    ]
    items.sort(key=lambda x: x.updated_at, reverse=True)
    return SessionListResponse(sessions=items)


@router.get("/sessions/{session_id}", response_model=SessionLoadResponse)
async def load_session(
    session_id: str,
    service: ChatService = Depends(get_chat_service),
) -> SessionLoadResponse:
    session = service.load_session_full(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Build session meta
    meta = SessionMetaResponse(
        id=session.id,
        title=session.title,
        created_at=session.created_at,
        updated_at=session.updated_at,
        message_count=session.message_count,
    )

    # Convert SessionMessage to frontend-friendly format
    messages: list[dict] = []
    for msg in session.messages:
        msg_dict: dict = {"type": msg.type, "content": str(msg.content) if msg.content else ""}
        if msg.tool_name:
            msg_dict["tool_name"] = msg.tool_name
        if msg.tool_call_id:
            msg_dict["tool_call_id"] = msg.tool_call_id
        messages.append(msg_dict)

    return SessionLoadResponse(session=meta, messages=messages)


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    service: ChatService = Depends(get_chat_service),
) -> dict:
    ok = service.delete_session(session_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"detail": "ok"}
