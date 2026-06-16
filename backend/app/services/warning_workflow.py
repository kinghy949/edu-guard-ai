"""预警处理工作流：状态机 + 跟进记录。

状态机：
- open → following / resolved / ignored
- following → resolved / ignored
- resolved / ignored → reopen → open
- comment：任意非终止状态可用，不改变 status
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException
from fastapi import status as http_status
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.warning import Warning, WarningAction, WarningActionType, WarningStatus

# 合法的状态流转
_TRANSITIONS: dict[str, dict[str, str]] = {
    WarningStatus.OPEN: {
        WarningActionType.FOLLOW: WarningStatus.FOLLOWING,
        WarningActionType.RESOLVE: WarningStatus.RESOLVED,
        WarningActionType.IGNORE: WarningStatus.IGNORED,
    },
    WarningStatus.FOLLOWING: {
        WarningActionType.RESOLVE: WarningStatus.RESOLVED,
        WarningActionType.IGNORE: WarningStatus.IGNORED,
    },
    WarningStatus.RESOLVED: {
        WarningActionType.REOPEN: WarningStatus.OPEN,
    },
    WarningStatus.IGNORED: {
        WarningActionType.REOPEN: WarningStatus.OPEN,
    },
}


def apply_action(
    db: Session,
    warning: Warning,
    user: User | None,
    action: str,
    note: str | None = None,
) -> WarningAction:
    if action not in {a.value for a in WarningActionType}:
        raise HTTPException(http_status.HTTP_400_BAD_REQUEST, f"未知操作类型: {action}")

    current = warning.status or WarningStatus.OPEN

    if action == WarningActionType.COMMENT:
        # 仅留言不改状态；终止态也允许补留言（便于事后归档说明）
        pass
    else:
        allowed = _TRANSITIONS.get(current, {})
        if action not in allowed:
            raise HTTPException(
                http_status.HTTP_409_CONFLICT,
                f"当前状态 {current}，不可执行 {action}",
            )
        new_status = allowed[action]
        warning.status = new_status

        # 副作用映射
        if action == WarningActionType.FOLLOW and user is not None:
            warning.assignee_id = user.id
        elif action == WarningActionType.RESOLVE:
            warning.resolved_at = datetime.now(timezone.utc)
            if note:
                warning.resolver_note = note
        elif action == WarningActionType.REOPEN:
            warning.resolved_at = None
            warning.resolver_note = None
            warning.assignee_id = user.id if user else None

    entry = WarningAction(
        warning_id=warning.id,
        user_id=user.id if user else None,
        action=action,
        note=note,
    )
    db.add(entry)
    db.flush()
    return entry
