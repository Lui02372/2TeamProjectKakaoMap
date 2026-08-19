from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.auth.models import AuthUser
from app.auth.service import require_current_session
from app.chat.intent_service import IntentService
from app.chat.models import ChatMessage, ChatMessageRequest, ChatResponse, ChatThread
from app.chat.repository import ThreadNotFoundError, create_chat_repository
from app.chat.service import ChatService
from app.routers.place_router import get_place_search_service


chat_router = APIRouter(prefix="/api/chat", tags=["Chat"])


def get_chat_service(request: Request) -> ChatService:
    return ChatService(create_chat_repository(), IntentService.from_settings(), get_place_search_service(request))


@chat_router.post("/threads", response_model=ChatThread, status_code=status.HTTP_201_CREATED)
def create_thread(user: Annotated[AuthUser, Depends(require_current_session)], service: Annotated[ChatService, Depends(get_chat_service)]) -> ChatThread:
    return service.create_thread(user.id)


@chat_router.get("/threads", response_model=list[ChatThread])
def list_threads(user: Annotated[AuthUser, Depends(require_current_session)], service: Annotated[ChatService, Depends(get_chat_service)]) -> list[ChatThread]:
    return service.list_threads(user.id)


@chat_router.get("/threads/{thread_id}/messages", response_model=list[ChatMessage])
def list_messages(thread_id: UUID, user: Annotated[AuthUser, Depends(require_current_session)], service: Annotated[ChatService, Depends(get_chat_service)]) -> list[ChatMessage]:
    try:
        return service.list_messages(user.id, thread_id)
    except ThreadNotFoundError as error:
        raise HTTPException(status_code=404, detail="대화를 찾을 수 없습니다.") from error


@chat_router.post("/threads/{thread_id}/messages", response_model=ChatResponse)
async def ask(thread_id: UUID, payload: ChatMessageRequest, user: Annotated[AuthUser, Depends(require_current_session)], service: Annotated[ChatService, Depends(get_chat_service)]) -> ChatResponse:
    try:
        return await service.ask(user.id, thread_id, payload)
    except ThreadNotFoundError as error:
        raise HTTPException(status_code=404, detail="대화를 찾을 수 없습니다.") from error
