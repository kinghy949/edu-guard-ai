"""导入回滚：把某次 import_batch 的写入逆向撤销。

约束：
- 仅允许 status='completed' 的批次回滚
- 同 kind 存在更晚批次时拒绝（避免覆盖更新的数据）
- 学生批次：create 行需级联删除其 User；若已有成绩/预警关联则跳过
- update 行：按 before JSONB 还原变更字段；Decimal 类型按字符串还原
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.course import Course
from app.models.grade import Grade
from app.models.import_batch import ImportBatch, ImportBatchRow
from app.models.program import CreditBucket, Program, ProgramCourse
from app.models.student import Student
from app.models.user import User
from app.models.warning import Warning

log = get_logger("import_rollback")

# table_name → 模型类，及对应 Decimal 字段名集合（before 中以字符串存储，回写时需转回 Decimal）
_TABLE_MODELS: dict[str, tuple[type, set[str]]] = {
    "students": (Student, set()),
    "courses": (Course, {"credits"}),
    "programs": (Program, {"total_credits_required"}),
    "credit_buckets": (CreditBucket, {"credits_required"}),
    "program_courses": (ProgramCourse, set()),
    "grades": (Grade, {"credits_earned", "score"}),
}


def _to_field_value(table: str, field_name: str, raw: Any) -> Any:
    """JSONB 中拿出来的值还原成 SQLAlchemy 字段期望的 Python 类型。"""
    if raw is None:
        return None
    _, decimal_fields = _TABLE_MODELS[table]
    if field_name in decimal_fields and not isinstance(raw, Decimal):
        return Decimal(str(raw))
    return raw


def rollback_batch(db: Session, batch_id: int, operator_id: int | None) -> dict[str, Any]:
    batch = db.get(ImportBatch, batch_id)
    if not batch:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "批次不存在")
    if batch.status != "completed":
        raise HTTPException(status.HTTP_409_CONFLICT, f"批次状态 {batch.status}，不可回滚")
    later = db.scalar(select(ImportBatch).where(
        ImportBatch.kind == batch.kind,
        ImportBatch.status == "completed",
        ImportBatch.id > batch.id,
    ))
    if later is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"同类型存在更晚批次 #{later.id}，回滚会覆盖更新数据，已拒绝",
        )

    rows = list(db.scalars(
        select(ImportBatchRow)
        .where(ImportBatchRow.batch_id == batch.id)
        .order_by(ImportBatchRow.id.desc())
    ))

    restored = deleted = skipped = 0
    skipped_details: list[dict[str, Any]] = []

    for row in rows:
        model_cls, _ = _TABLE_MODELS.get(row.table_name, (None, set()))
        if model_cls is None:
            skipped += 1
            skipped_details.append({"row": row.row_no, "reason": f"未知表 {row.table_name}"})
            continue
        if row.record_pk is None:
            skipped += 1
            skipped_details.append({"row": row.row_no, "reason": "记录主键缺失"})
            continue
        obj = db.get(model_cls, row.record_pk)
        if obj is None:
            skipped += 1
            skipped_details.append({"row": row.row_no, "reason": f"{row.table_name}#{row.record_pk} 已不存在"})
            continue

        if row.op == "create":
            # 学生需级联删除其关联 User；若学生已有成绩/预警则跳过
            if row.table_name == "students":
                has_grade = db.scalar(select(Grade.id).where(Grade.student_id == obj.id))
                has_warning = db.scalar(select(Warning.id).where(Warning.student_id == obj.id))
                if has_grade or has_warning:
                    skipped += 1
                    skipped_details.append({
                        "row": row.row_no,
                        "reason": f"学生 {obj.student_no} 已有成绩或预警，跳过删除",
                    })
                    continue
                user_id = obj.user_id
                db.delete(obj)
                if user_id:
                    user = db.get(User, user_id)
                    if user:
                        db.delete(user)
            elif row.table_name == "courses":
                # 课程被任何 program_courses / grades 引用则跳过
                in_prog = db.scalar(select(ProgramCourse.id).where(ProgramCourse.course_id == obj.id))
                in_grade = db.scalar(select(Grade.id).where(Grade.course_id == obj.id))
                if in_prog or in_grade:
                    skipped += 1
                    skipped_details.append({
                        "row": row.row_no,
                        "reason": f"课程 {obj.code} 已被引用，跳过删除",
                    })
                    continue
                db.delete(obj)
            else:
                db.delete(obj)
            deleted += 1
        elif row.op == "update":
            before = row.before or {}
            for field, value in before.items():
                setattr(obj, field, _to_field_value(row.table_name, field, value))
            restored += 1
        else:
            skipped += 1
            skipped_details.append({"row": row.row_no, "reason": f"未知操作 {row.op}"})

    batch.status = "rolled_back"
    log.info(
        "import_rollback", batch_id=batch.id, kind=batch.kind,
        restored=restored, deleted=deleted, skipped=skipped,
        operator_id=operator_id,
    )
    db.commit()
    return {"restored": restored, "deleted": deleted, "skipped": skipped, "skipped_details": skipped_details}
