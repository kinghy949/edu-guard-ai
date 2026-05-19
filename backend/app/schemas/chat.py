from app.schemas._base import ORMBase, TimestampRead


class ChatSessionRead(TimestampRead):
    user_id: int
    title: str | None


class ChatMessageRead(TimestampRead):
    session_id: int
    role: str
    content: str


class ChatMessageCreate(ORMBase):
    session_id: int
    role: str = "user"
    content: str
