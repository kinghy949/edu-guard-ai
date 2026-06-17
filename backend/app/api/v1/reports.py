from datetime import datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession, require_staff
from app.models.snapshot import StudentProgressSnapshot
from app.models.student import Student
from app.models.warning import Warning, WarningStatus
from app.services.audit import record_audit
from app.services.exporter import SheetSpec, build_workbook
from app.services.stats import class_ranking

router = APIRouter(dependencies=[Depends(require_staff)])

_XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _stream(buf, name_prefix: str):
    fname = f"{name_prefix}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    return StreamingResponse(
        buf,
        media_type=_XLSX_MIME,
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


@router.get("/warnings.xlsx", summary="预警明细 Excel")
def export_warnings(
    db: DbSession, current: CurrentUser, request: Request,
    semester: str | None = None, level: str | None = None, status: str | None = None,
    college: str | None = None, class_name: str | None = None,
):
    stmt = (
        select(
            Student.student_no, Student.name, Student.class_name,
            Warning.level, Warning.status, Warning.semester, Warning.summary,
            Warning.created_at, Warning.resolved_at, Warning.resolver_note,
        )
        .join(Student, Student.id == Warning.student_id)
    )
    if semester:
        stmt = stmt.where(Warning.semester == semester)
    if level:
        stmt = stmt.where(Warning.level == level)
    if status:
        stmt = stmt.where(Warning.status == status)
    if college:
        stmt = stmt.where(Student.college == college)
    if class_name:
        stmt = stmt.where(Student.class_name == class_name)
    rows = [
        [no, name, cls, lvl, st, sem, summary,
         created.strftime("%Y-%m-%d %H:%M") if created else "",
         resolved.strftime("%Y-%m-%d %H:%M") if resolved else "",
         note or ""]
        for no, name, cls, lvl, st, sem, summary, created, resolved, note
        in db.execute(stmt.order_by(Warning.created_at.desc()))
    ]
    sheet = SheetSpec(
        title="预警明细",
        headers=["学号", "姓名", "班级", "级别", "状态", "学期", "摘要",
                 "生成时间", "解决时间", "处理备注"],
        rows=rows,
    )
    record_audit(db, user=current, action="reports.export",
                 resource_type="report", resource_id="warnings",
                 detail={"rows": len(rows)}, request=request)
    db.commit()
    return _stream(build_workbook([sheet]), "warnings")


@router.get("/completion.xlsx", summary="学业完成度 Excel")
def export_completion(
    db: DbSession, current: CurrentUser, request: Request,
    college: str | None = None, enroll_year: int | None = None,
    class_name: str | None = None,
):
    open_status = (WarningStatus.OPEN, WarningStatus.FOLLOWING)
    stmt = (
        select(Student, StudentProgressSnapshot)
        .outerjoin(StudentProgressSnapshot, StudentProgressSnapshot.student_id == Student.id)
    )
    if college:
        stmt = stmt.where(Student.college == college)
    if enroll_year is not None:
        stmt = stmt.where(Student.enroll_year == enroll_year)
    if class_name:
        stmt = stmt.where(Student.class_name == class_name)

    rows = []
    for student, snap in db.execute(stmt.order_by(Student.student_no)):
        highest = db.scalar(
            select(Warning.level)
            .where(Warning.student_id == student.id, Warning.status.in_(open_status))
            .order_by(
                # severe>warn>info 排在前面：用 CASE 不优雅，直接按级别取 max 字符串
                Warning.level.desc()
            )
            .limit(1)
        )
        rows.append([
            student.student_no, student.name, student.class_name or "",
            str(snap.total_required) if snap else "",
            str(snap.total_earned) if snap else "",
            str(snap.total_in_progress) if snap else "",
            str(snap.total_gap) if snap else "",
            f"{round((snap.completion_ratio or 0) * 100)}%" if snap else "",
            snap.failed_count if snap else "",
            highest or "",
        ])
    sheet = SheetSpec(
        title="学业完成度",
        headers=["学号", "姓名", "班级", "总要求", "已修", "在修", "缺口",
                 "完成度", "挂科数", "最高未处理预警"],
        rows=rows,
    )
    record_audit(db, user=current, action="reports.export",
                 resource_type="report", resource_id="completion",
                 detail={"rows": len(rows)}, request=request)
    db.commit()
    return _stream(build_workbook([sheet]), "completion")


@router.get("/class-summary.xlsx", summary="班级汇总 Excel")
def export_class_summary(
    db: DbSession, current: CurrentUser, request: Request,
    college: str | None = None, enroll_year: int | None = None,
):
    data = class_ranking(db, college=college, enroll_year=enroll_year)
    rows = [
        [d["class_name"], d["students"],
         f"{round(d['avg_completion_ratio'] * 100)}%",
         d["open_warnings"], d["severe_warnings"]]
        for d in data
    ]
    sheet = SheetSpec(
        title="班级汇总",
        headers=["班级", "人数", "平均完成度", "未处理预警", "严重预警"],
        rows=rows,
    )
    record_audit(db, user=current, action="reports.export",
                 resource_type="report", resource_id="class_summary",
                 detail={"rows": len(rows)}, request=request)
    db.commit()
    return _stream(build_workbook([sheet]), "class_summary")
