"""学业进度快照 + 大盘统计。

性能取舍：千人级试点直接 SQL 聚合即可；快照表用于避免每次大盘都
重算 N 个学生的 credit_compare（compute_student_progress 涉及多次 join）。
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Iterable

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models.snapshot import StudentProgressSnapshot
from app.models.student import Student
from app.models.warning import Warning, WarningStatus
from app.services.credit_compare import compute_student_progress


def refresh_snapshots(db: Session, student_ids: Iterable[int] | None = None) -> int:
    """重算指定学生（或全部）的进度快照，upsert 到 student_progress_snapshots。"""
    stmt = select(Student)
    if student_ids is not None:
        ids = list(student_ids)
        if not ids:
            return 0
        stmt = stmt.where(Student.id.in_(ids))
    students = list(db.scalars(stmt))
    now = datetime.now(timezone.utc)
    for s in students:
        report = compute_student_progress(db, s)
        snap = db.get(StudentProgressSnapshot, s.id)
        ratio = 0.0
        if report.total_required > 0:
            ratio = float((report.total_earned + report.total_in_progress) / report.total_required)
        data = dict(
            total_required=report.total_required,
            total_earned=report.total_earned,
            total_in_progress=report.total_in_progress,
            total_gap=report.total_gap,
            completion_ratio=min(max(ratio, 0.0), 1.0),
            failed_count=len(report.failed_courses),
            computed_at=now,
        )
        if snap is None:
            snap = StudentProgressSnapshot(student_id=s.id, **data)
            db.add(snap)
        else:
            for k, v in data.items():
                setattr(snap, k, v)
    db.commit()
    return len(students)


def overview(db: Session, college: str | None = None) -> dict[str, Any]:
    """大盘指标：学生总数、各级未处理预警数、平均完成度、挂科学生数。"""
    student_q = select(Student)
    if college:
        student_q = student_q.where(Student.college == college)
    students_total = db.scalar(select(func.count()).select_from(student_q.subquery())) or 0

    open_status = (WarningStatus.OPEN, WarningStatus.FOLLOWING)
    w_q = select(Warning.level, func.count(Warning.id)).where(Warning.status.in_(open_status))
    if college:
        w_q = w_q.join(Student, Student.id == Warning.student_id).where(Student.college == college)
    w_q = w_q.group_by(Warning.level)
    warnings_open = {"info": 0, "warn": 0, "severe": 0}
    for level, cnt in db.execute(w_q):
        warnings_open[level] = int(cnt)

    # 已处理比率
    total_w = db.scalar(select(func.count(Warning.id))) or 0
    resolved_w = db.scalar(
        select(func.count(Warning.id)).where(Warning.status == WarningStatus.RESOLVED)
    ) or 0
    warnings_resolved_ratio = (resolved_w / total_w) if total_w else 0.0

    # 平均完成度（仅含已快照学生）
    snap_q = select(func.avg(StudentProgressSnapshot.completion_ratio))
    if college:
        snap_q = snap_q.join(Student, Student.id == StudentProgressSnapshot.student_id)\
                       .where(Student.college == college)
    avg_completion = db.scalar(snap_q) or 0.0

    failed_students = db.scalar(
        select(func.count(StudentProgressSnapshot.student_id))
        .where(StudentProgressSnapshot.failed_count > 0)
    ) or 0

    return {
        "students_total": int(students_total),
        "warnings_open": warnings_open,
        "warnings_resolved_ratio": round(float(warnings_resolved_ratio), 4),
        "avg_completion_ratio": round(float(avg_completion), 4),
        "failed_students": int(failed_students),
    }


def warning_trend(db: Session, semesters: int = 6) -> list[dict[str, Any]]:
    """按 semester 分组的各级预警计数（取最近 N 个出现过的学期）。"""
    rows = list(db.execute(
        select(Warning.semester, Warning.level, func.count(Warning.id))
        .group_by(Warning.semester, Warning.level)
        .order_by(Warning.semester.desc())
    ))
    by_sem: dict[str, dict[str, int]] = {}
    for sem, level, cnt in rows:
        by_sem.setdefault(sem, {"info": 0, "warn": 0, "severe": 0})[level] = int(cnt)
    semesters_sorted = sorted(by_sem.keys(), reverse=True)[:semesters]
    semesters_sorted.reverse()
    return [{"semester": s, **by_sem[s]} for s in semesters_sorted]


def class_ranking(
    db: Session, college: str | None = None, enroll_year: int | None = None,
) -> list[dict[str, Any]]:
    """班级维度统计：人数 / 平均完成度 / 未处理预警数 / severe 数。"""
    open_status = (WarningStatus.OPEN, WarningStatus.FOLLOWING)
    severe_case = case(
        (Warning.level == "severe", 1), else_=0,
    )
    open_case = case(
        (Warning.status.in_(open_status), 1), else_=0,
    )
    stmt = (
        select(
            Student.class_name,
            func.count(func.distinct(Student.id)).label("students"),
            func.avg(StudentProgressSnapshot.completion_ratio).label("avg_completion"),
            func.coalesce(func.sum(open_case), 0).label("open_warnings"),
            func.coalesce(func.sum(severe_case), 0).label("severe_warnings"),
        )
        .select_from(Student)
        .outerjoin(StudentProgressSnapshot, StudentProgressSnapshot.student_id == Student.id)
        .outerjoin(Warning, Warning.student_id == Student.id)
        .group_by(Student.class_name)
    )
    if college:
        stmt = stmt.where(Student.college == college)
    if enroll_year is not None:
        stmt = stmt.where(Student.enroll_year == enroll_year)
    rows = []
    for class_name, students, avg_c, open_w, severe_w in db.execute(stmt):
        if class_name is None:
            continue
        rows.append({
            "class_name": class_name,
            "students": int(students),
            "avg_completion_ratio": round(float(avg_c or 0), 4),
            "open_warnings": int(open_w or 0),
            "severe_warnings": int(severe_w or 0),
        })
    rows.sort(key=lambda x: x["avg_completion_ratio"])
    return rows


def level_distribution(db: Session, dim: str = "college") -> list[dict[str, Any]]:
    """按指定维度（college/major/class_name）聚合各级预警数。"""
    if dim not in {"college", "major", "class_name"}:
        raise ValueError("dim must be one of college/major/class_name")
    dim_col = getattr(Student, dim)
    stmt = (
        select(dim_col, Warning.level, func.count(Warning.id))
        .join(Student, Student.id == Warning.student_id)
        .group_by(dim_col, Warning.level)
    )
    bucket: dict[str, dict[str, int]] = {}
    for value, level, cnt in db.execute(stmt):
        if value is None:
            continue
        bucket.setdefault(value, {"info": 0, "warn": 0, "severe": 0})[level] = int(cnt)
    return [{"key": k, **v} for k, v in sorted(bucket.items())]


def latest_snapshot_age_seconds(db: Session) -> int | None:
    """快照最近一次刷新时间距今秒数，None 表示从未刷新。"""
    latest = db.scalar(select(func.max(StudentProgressSnapshot.computed_at)))
    if latest is None:
        return None
    return int((datetime.now(timezone.utc) - latest).total_seconds())


def _safe_decimal(v: Any) -> Decimal:
    try:
        return Decimal(str(v))
    except Exception:
        return Decimal("0")
