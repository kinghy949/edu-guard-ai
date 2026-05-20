import json
from typing import AsyncIterator

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select

from app.ai import LLMError, NO_CONTEXT_HINT, SYSTEM_PROMPT, build_student_context, chat, chat_stream, load_runtime
from app.api.deps import CurrentUser, DbSession
from app.api.v1._helpers import get_or_404
from app.models.chat import ChatMessage, ChatSession
from app.models.student import Student
from app.models.user import UserRole
from app.schemas.chat import ChatMessageRead, ChatSessionRead

router = APIRouter()

MAX_HISTORY = 20  # 截取最近 N 条作为上下文


class CreateSessionRequest(BaseModel):
    title: str | None = None


class SendMessageRequest(BaseModel):
    content: str


def _ensure_owner(session: ChatSession, current) -> None:
    if session.user_id != current.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "无权访问该会话")


def _build_messages(db, current, session: ChatSession, user_input: str) -> list[dict[str, str]]:
    system_parts = [SYSTEM_PROMPT]
    if current.role == UserRole.STUDENT:
        student = db.scalar(select(Student).where(Student.user_id == current.id))
        if student:
            system_parts.append(build_student_context(db, student))
        else:
            system_parts.append(NO_CONTEXT_HINT)
    else:
        system_parts.append("当前用户为教职工，回答可更宏观，但仍仅依据真实数据。")

    messages = [{"role": "system", "content": "\n\n".join(system_parts)}]

    history = db.scalars(
        select(ChatMessage)
        .where(ChatMessage.session_id == session.id)
        .order_by(ChatMessage.created_at.desc())
        .limit(MAX_HISTORY)
    ).all()
    for m in reversed(history):
        messages.append({"role": m.role, "content": m.content})
    messages.append({"role": "user", "content": user_input})
    return messages


@router.get("/sessions", response_model=list[ChatSessionRead])
def list_sessions(db: DbSession, current: CurrentUser):
    return db.scalars(
        select(ChatSession)
        .where(ChatSession.user_id == current.id)
        .order_by(ChatSession.updated_at.desc())
    ).all()


@router.post("/sessions", response_model=ChatSessionRead)
def create_session(payload: CreateSessionRequest, db: DbSession, current: CurrentUser):
    session = ChatSession(user_id=current.id, title=payload.title or "新会话")
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


@router.get("/sessions/{session_id}/messages", response_model=list[ChatMessageRead])
def list_messages(session_id: int, db: DbSession, current: CurrentUser):
    session = get_or_404(db, ChatSession, session_id, "会话")
    _ensure_owner(session, current)
    return db.scalars(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
    ).all()


@router.post("/sessions/{session_id}/messages", response_model=ChatMessageRead)
def send_message(session_id: int, payload: SendMessageRequest, db: DbSession, current: CurrentUser):
    session = get_or_404(db, ChatSession, session_id, "会话")
    _ensure_owner(session, current)

    db.add(ChatMessage(session_id=session.id, role="user", content=payload.content))
    db.flush()

    messages = _build_messages(db, current, session, payload.content)
    try:
        runtime = load_runtime(db)
        reply = chat(messages, runtime=runtime)
    except LLMError as e:
        db.rollback()
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(e)) from e

    assistant_msg = ChatMessage(session_id=session.id, role="assistant", content=reply)
    db.add(assistant_msg)
    db.commit()
    db.refresh(assistant_msg)
    return assistant_msg


@router.post("/sessions/{session_id}/messages/stream", summary="流式回答（SSE）")
async def stream_message(session_id: int, payload: SendMessageRequest, db: DbSession, current: CurrentUser):
    session = get_or_404(db, ChatSession, session_id, "会话")
    _ensure_owner(session, current)

    db.add(ChatMessage(session_id=session.id, role="user", content=payload.content))
    db.commit()

    messages = _build_messages(db, current, session, payload.content)
    runtime = load_runtime(db)

    async def gen() -> AsyncIterator[bytes]:
        chunks: list[str] = []
        try:
            async for delta in chat_stream(messages, runtime=runtime):
                chunks.append(delta)
                # JSON 编码以兼容 delta 内含换行符等
                yield f"data: {json.dumps({'delta': delta}, ensure_ascii=False)}\n\n".encode("utf-8")
        except LLMError as e:
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n".encode("utf-8")
            return
        final = "".join(chunks)
        if final:
            db.add(ChatMessage(session_id=session.id, role="assistant", content=final))
            db.commit()
        yield b"event: done\ndata: {}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(session_id: int, db: DbSession, current: CurrentUser):
    session = get_or_404(db, ChatSession, session_id, "会话")
    _ensure_owner(session, current)
    db.delete(session)
    db.commit()
