from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession, require_staff
from app.api.v1._helpers import get_or_404
from app.core.logging import get_logger
from app.models.student import Student
from app.models.user import UserRole
from app.models.warning import Warning, WarningAction, WarningActionType
from app.schemas.warning import WarningActionCreate, WarningActionRead, WarningRead
from app.services.audit import record_audit
from app.services.notify_dispatcher import dispatch_warning
from app.services.warning_engine import generate_batch, generate_for_student
from app.services.warning_workflow import apply_action

log = get_logger("warnings")

router = APIRouter()


class GenerateRequest(BaseModel):
    student_ids: list[int] | None = None  # 空 = 全部
    semester: str | None = None
    college: str | None = None
    major: str | None = None
    enroll_year: int | None = None
    auto_dispatch: bool = False
    channels: list[str] | None = None


class ResolveRequest(BaseModel):
    note: str | None = None


@router.get("", response_model=list[WarningRead])
def list_warnings(
    db: DbSession,
    current: CurrentUser,
    student_id: int | None = None,
    level: str | None = None,
    semester: str | None = None,
    status_: str | None = None,
    assignee_id: int | None = None,
    only_open: bool = False,
    skip: int = 0,
    limit: int = 100,
):
    stmt = select(Warning)
    if current.role == UserRole.STUDENT:
        me = db.scalar(select(Student).where(Student.user_id == current.id))
        if not me:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "未关联学生信息")
        stmt = stmt.where(Warning.student_id == me.id)
    elif student_id is not None:
        stmt = stmt.where(Warning.student_id == student_id)

    if level:
        stmt = stmt.where(Warning.level == level)
    if semester:
        stmt = stmt.where(Warning.semester == semester)
    if status_:
        stmt = stmt.where(Warning.status == status_)
    if assignee_id is not None:
        stmt = stmt.where(Warning.assignee_id == assignee_id)
    if only_open:
        stmt = stmt.where(Warning.status.in_(["open", "following"]))

    return db.scalars(stmt.order_by(Warning.created_at.desc()).offset(skip).limit(limit)).all()


@router.get("/{warning_id}", response_model=WarningRead)
def get_warning(warning_id: int, db: DbSession, current: CurrentUser):
    w = get_or_404(db, Warning, warning_id, "预警")
    if current.role == UserRole.STUDENT:
        me = db.scalar(select(Student).where(Student.user_id == current.id))
        if not me or me.id != w.student_id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "无权访问该预警")
    return w


@router.post("/generate", dependencies=[Depends(require_staff)], summary="批量生成预警")
def generate(payload: GenerateRequest, db: DbSession, current: CurrentUser, request: Request):
    stmt = select(Student)
    if payload.student_ids:
        stmt = stmt.where(Student.id.in_(payload.student_ids))
    if payload.college:
        stmt = stmt.where(Student.college == payload.college)
    if payload.major:
        stmt = stmt.where(Student.major == payload.major)
    if payload.enroll_year is not None:
        stmt = stmt.where(Student.enroll_year == payload.enroll_year)
    students = list(db.scalars(stmt))
    if not students:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "未匹配到学生")
    result = generate_batch(db, students, semester=payload.semester)
    log.info(
        "warnings_generated",
        semester=result.get("semester"), student_count=len(students),
        created=result.get("created", 0), updated=result.get("updated", 0),
        auto_dispatch=bool(payload.auto_dispatch),
    )
    if payload.auto_dispatch:
        dispatched = queued = sent = failed = 0
        for w in db.scalars(select(Warning).where(
            Warning.semester == result["semester"],
            Warning.student_id.in_([s.id for s in students]),
        )):
            s = dispatch_warning(db, w, channels=payload.channels)
            dispatched += 1
            queued += s.queued
            sent += s.sent
            failed += s.failed
        result["dispatched"] = {"warnings": dispatched, "queued": queued, "sent": sent, "failed": failed}
    record_audit(
        db, user=current, action="warnings.generate",
        detail={
            "semester": result.get("semester"),
            "student_count": len(students),
            "created": result.get("created"),
            "updated": result.get("updated"),
            "auto_dispatch": bool(payload.auto_dispatch),
        },
        request=request,
    )
    db.commit()
    return result


@router.post("/students/{student_id}/generate", dependencies=[Depends(require_staff)], summary="单学生触发预警")
def generate_one(student_id: int, db: DbSession, semester: str | None = None):
    student = get_or_404(db, Student, student_id, "学生")
    w = generate_for_student(db, student, semester=semester)
    if not w:
        db.commit()
        return {"generated": False, "reason": "完成度达标，无需预警"}
    db.commit()
    db.refresh(w)
    return {"generated": True, "warning_id": w.id, "level": w.level, "summary": w.summary}


@router.post("/{warning_id}/resolve", response_model=WarningRead, dependencies=[Depends(require_staff)])
def resolve(warning_id: int, payload: ResolveRequest, db: DbSession, current: CurrentUser, request: Request):
    """兼容入口：等价于 actions(action=resolve)，保留旧调用方式。"""
    w = get_or_404(db, Warning, warning_id, "预警")
    apply_action(db, w, current, WarningActionType.RESOLVE, payload.note)
    record_audit(
        db, user=current, action="warnings.resolve",
        resource_type="warning", resource_id=warning_id,
        detail={"note": payload.note}, request=request,
    )
    db.commit()
    db.refresh(w)
    return w


@router.post(
    "/{warning_id}/actions",
    response_model=WarningRead,
    dependencies=[Depends(require_staff)],
    summary="对预警执行处理流操作（comment/follow/resolve/ignore/reopen）",
)
def execute_action(
    warning_id: int, payload: WarningActionCreate, db: DbSession,
    current: CurrentUser, request: Request,
):
    w = get_or_404(db, Warning, warning_id, "预警")
    apply_action(db, w, current, payload.action, payload.note)
    record_audit(
        db, user=current, action=f"warnings.action.{payload.action}",
        resource_type="warning", resource_id=warning_id,
        detail={"note": payload.note, "new_status": w.status},
        request=request,
    )
    db.commit()
    db.refresh(w)
    return w


@router.get(
    "/{warning_id}/actions",
    response_model=list[WarningActionRead],
    dependencies=[Depends(require_staff)],
    summary="查看预警跟进时间线（staff 专用）",
)
def list_actions(warning_id: int, db: DbSession):
    # 仅 staff 可见，学生不参与工作流细节
    get_or_404(db, Warning, warning_id, "预警")
    rows = db.scalars(
        select(WarningAction)
        .where(WarningAction.warning_id == warning_id)
        .order_by(WarningAction.id.desc())
    )
    return [WarningActionRead.model_validate(r) for r in rows]
