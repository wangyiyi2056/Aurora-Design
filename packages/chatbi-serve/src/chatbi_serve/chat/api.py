from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from chatbi_serve.chat.schema import ChatRequest, ChatResponse
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
