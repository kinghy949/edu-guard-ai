"""教务数据批量导入。

- 入口接受 ``bytes`` + 文件后缀，自动用 pandas 解析为 DataFrame。
- 每个 ``import_*`` 函数返回 ``ImportResult``：created/updated/skipped/errors/rows。
- ``run_import`` 是统一入口：包装事务、登记 ``import_batches``、支持 dry-run（savepoint 回滚业务写入但保留批次记录）。
"""
from __future__ import annotations

import io
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.core.security import hash_password
from app.models.course import Course
from app.models.grade import Grade, GradeStatus
from app.models.import_batch import ImportBatch, ImportBatchRow
from app.models.program import CreditBucket, Program, ProgramCourse
from app.models.student import Student
from app.models.user import User, UserRole

log = get_logger("importer")


@dataclass
class RowChange:
    """单行写入痕迹，供导入历史与回滚使用。"""
    row_no: int | None
    op: str  # create / update
    table_name: str
    record_pk: int | None
    before: dict[str, Any] | None = None  # update 时填变更字段旧值


@dataclass
class ImportResult:
    created: int = 0
    updated: int = 0
    skipped: int = 0
    errors: list[dict[str, Any]] = field(default_factory=list)
    rows: list[RowChange] = field(default_factory=list)

    def add_error(self, row: int, message: str) -> None:
        self.errors.append({"row": row, "message": message})

    def add_row(self, change: RowChange) -> None:
        self.rows.append(change)


def _snapshot_before(obj: Any, fields: tuple[str, ...]) -> dict[str, Any]:
    """对 SQLAlchemy 模型对象抓取指定字段当前值（即将被覆盖的旧值）。"""
    snap: dict[str, Any] = {}
    for f in fields:
        v = getattr(obj, f, None)
        # Decimal / datetime 等无法直接进 JSONB，统一字符串化
        if isinstance(v, Decimal):
            snap[f] = str(v)
        else:
            snap[f] = v if v is None or isinstance(v, (str, int, float, bool)) else str(v)
    return snap


def parse_table(content: bytes, filename: str) -> pd.DataFrame:
    """根据文件后缀解析为 DataFrame。"""
    name = filename.lower()
    buf = io.BytesIO(content)
    if name.endswith(".csv"):
        return pd.read_csv(buf, dtype=str, keep_default_na=False)
    if name.endswith((".xlsx", ".xls")):
        return pd.read_excel(buf, dtype=str, keep_default_na=False)
    raise ValueError("仅支持 .csv / .xlsx / .xls")


def apply_mapping(df: pd.DataFrame, mapping: dict[str, str] | None) -> pd.DataFrame:
    """按 {源列名: 目标字段} 重命名列；未映射且非目标列名的多余列保留原名（importer 自会忽略）。"""
    if not mapping:
        return df
    # 仅对真正出现在 df 中的源列做 rename，避免 pandas 抛 KeyError
    valid = {src: dst for src, dst in mapping.items() if src in df.columns}
    return df.rename(columns=valid)


def _row(df_row: pd.Series) -> dict[str, str]:
    return {k: (str(v).strip() if v is not None else "") for k, v in df_row.to_dict().items()}


def _require(row: dict[str, str], *keys: str) -> str | None:
    for k in keys:
        if not row.get(k):
            return f"缺少必填字段: {k}"
    return None


def _to_decimal(value: str, field_name: str) -> Decimal:
    try:
        return Decimal(value)
    except (InvalidOperation, ValueError) as e:
        raise ValueError(f"{field_name} 不是合法数值: {value}") from e


# ----- 学生名册 -----

STUDENT_COLUMNS = ["student_no", "name", "enroll_year", "college", "major", "class_name", "gender", "email", "phone"]


def import_students(db: Session, df: pd.DataFrame, default_role: str = UserRole.STUDENT) -> ImportResult:
    """学号即用户名，初始密码 = 学号（生产请提醒首次登录修改）。"""
    result = ImportResult()
    for idx, raw in df.iterrows():
        row = _row(raw)
        line = int(idx) + 2  # 表头占第 1 行
        err = _require(row, "student_no", "name", "enroll_year", "college", "major")
        if err:
            result.add_error(line, err)
            continue
        try:
            enroll_year = int(row["enroll_year"])
        except ValueError:
            result.add_error(line, "enroll_year 必须为整数")
            continue

        student = db.scalar(select(Student).where(Student.student_no == row["student_no"]))
        if student:
            before = _snapshot_before(student, ("name", "gender", "college", "major", "class_name"))
            student.name = row["name"]
            student.gender = row.get("gender") or None
            student.college = row["college"]
            student.major = row["major"]
            student.class_name = row.get("class_name") or None
            result.updated += 1
            result.add_row(RowChange(line, "update", "students", student.id, before))
            continue

        user = User(
            username=row["student_no"],
            password_hash=hash_password(row["student_no"]),
            role=default_role,
            email=row.get("email") or None,
            phone=row.get("phone") or None,
            display_name=row["name"],
            # 学生初始密码=学号，必须首次登录后立即改密
            must_change_password=True,
        )
        db.add(user)
        db.flush()
        new_student = Student(
            user_id=user.id,
            student_no=row["student_no"],
            name=row["name"],
            gender=row.get("gender") or None,
            enroll_year=enroll_year,
            college=row["college"],
            major=row["major"],
            class_name=row.get("class_name") or None,
        )
        db.add(new_student)
        db.flush()
        result.created += 1
        result.add_row(RowChange(line, "create", "students", new_student.id))
    return result


# ----- 课程主数据 -----

COURSE_COLUMNS = ["code", "name", "credits", "hours", "category_default", "description"]


def import_courses(db: Session, df: pd.DataFrame) -> ImportResult:
    result = ImportResult()
    for idx, raw in df.iterrows():
        row = _row(raw)
        line = int(idx) + 2
        err = _require(row, "code", "name", "credits")
        if err:
            result.add_error(line, err)
            continue
        try:
            credits = _to_decimal(row["credits"], "credits")
        except ValueError as e:
            result.add_error(line, str(e))
            continue
        hours = int(row["hours"]) if row.get("hours") else None

        course = db.scalar(select(Course).where(Course.code == row["code"]))
        if course:
            before = _snapshot_before(course, ("name", "credits", "hours", "category_default", "description"))
            course.name = row["name"]
            course.credits = credits
            course.hours = hours
            course.category_default = row.get("category_default") or None
            course.description = row.get("description") or None
            result.updated += 1
            result.add_row(RowChange(line, "update", "courses", course.id, before))
        else:
            new_course = Course(
                code=row["code"],
                name=row["name"],
                credits=credits,
                hours=hours,
                category_default=row.get("category_default") or None,
                description=row.get("description") or None,
            )
            db.add(new_course)
            db.flush()
            result.created += 1
            result.add_row(RowChange(line, "create", "courses", new_course.id))
    return result


# ----- 培养方案（含学分桶 + 课程映射） -----

PROGRAM_COLUMNS = [
    "program_code", "program_name", "college", "major", "version", "total_credits",
    "course_code", "course_name", "credits", "category", "category_required_credits",
    "is_required", "semester_suggested",
]


def import_program(db: Session, df: pd.DataFrame) -> ImportResult:
    """单方案多行：每行一门课，方案与桶按表中字段去重。"""
    result = ImportResult()
    bucket_cache: dict[tuple[int, str], CreditBucket] = {}

    for idx, raw in df.iterrows():
        row = _row(raw)
        line = int(idx) + 2
        err = _require(row, "program_code", "program_name", "college", "major", "version",
                       "total_credits", "course_code", "category", "category_required_credits")
        if err:
            result.add_error(line, err)
            continue
        try:
            total_credits = _to_decimal(row["total_credits"], "total_credits")
            cat_required = _to_decimal(row["category_required_credits"], "category_required_credits")
        except ValueError as e:
            result.add_error(line, str(e))
            continue

        program = db.scalar(select(Program).where(Program.code == row["program_code"]))
        if not program:
            program = Program(
                code=row["program_code"],
                name=row["program_name"],
                college=row["college"],
                major=row["major"],
                version=row["version"],
                total_credits_required=total_credits,
            )
            db.add(program)
            db.flush()

        bucket_key = (program.id, row["category"])
        bucket = bucket_cache.get(bucket_key)
        if not bucket:
            bucket = db.scalar(select(CreditBucket).where(
                CreditBucket.program_id == program.id,
                CreditBucket.category == row["category"],
            ))
            if not bucket:
                bucket = CreditBucket(
                    program_id=program.id,
                    category=row["category"],
                    credits_required=cat_required,
                )
                db.add(bucket)
                db.flush()
            bucket_cache[bucket_key] = bucket

        course = db.scalar(select(Course).where(Course.code == row["course_code"]))
        if not course:
            if not row.get("course_name") or not row.get("credits"):
                result.add_error(line, "课程不存在且未提供 course_name/credits 用于创建")
                continue
            try:
                course_credits = _to_decimal(row["credits"], "credits")
            except ValueError as e:
                result.add_error(line, str(e))
                continue
            course = Course(code=row["course_code"], name=row["course_name"], credits=course_credits)
            db.add(course)
            db.flush()

        pc = db.scalar(select(ProgramCourse).where(
            ProgramCourse.program_id == program.id,
            ProgramCourse.course_id == course.id,
        ))
        is_required = row.get("is_required", "").lower() in {"1", "true", "y", "是", "必修"}
        sem = int(row["semester_suggested"]) if row.get("semester_suggested") else None
        if pc:
            before = _snapshot_before(pc, ("bucket_id", "is_required", "semester_suggested"))
            pc.bucket_id = bucket.id
            pc.is_required = is_required
            pc.semester_suggested = sem
            result.updated += 1
            result.add_row(RowChange(line, "update", "program_courses", pc.id, before))
        else:
            new_pc = ProgramCourse(
                program_id=program.id,
                course_id=course.id,
                bucket_id=bucket.id,
                is_required=is_required,
                semester_suggested=sem,
            )
            db.add(new_pc)
            db.flush()
            result.created += 1
            result.add_row(RowChange(line, "create", "program_courses", new_pc.id))
    return result


# ----- 成绩 -----

GRADE_COLUMNS = ["student_no", "course_code", "semester", "credits_earned", "score", "status"]

_STATUS_ALIASES = {
    "已完成": GradeStatus.COMPLETED, "completed": GradeStatus.COMPLETED, "通过": GradeStatus.COMPLETED,
    "在修": GradeStatus.IN_PROGRESS, "in_progress": GradeStatus.IN_PROGRESS,
    "挂科": GradeStatus.FAILED, "failed": GradeStatus.FAILED, "不及格": GradeStatus.FAILED,
    "重修": GradeStatus.RETAKE, "retake": GradeStatus.RETAKE,
}


def import_grades(db: Session, df: pd.DataFrame) -> ImportResult:
    result = ImportResult()
    for idx, raw in df.iterrows():
        row = _row(raw)
        line = int(idx) + 2
        err = _require(row, "student_no", "course_code", "semester")
        if err:
            result.add_error(line, err)
            continue

        student = db.scalar(select(Student).where(Student.student_no == row["student_no"]))
        if not student:
            result.add_error(line, f"学号不存在: {row['student_no']}")
            continue
        course = db.scalar(select(Course).where(Course.code == row["course_code"]))
        if not course:
            result.add_error(line, f"课程编码不存在: {row['course_code']}")
            continue

        try:
            credits_earned = _to_decimal(row["credits_earned"], "credits_earned") if row.get("credits_earned") else Decimal("0")
            score = _to_decimal(row["score"], "score") if row.get("score") else None
        except ValueError as e:
            result.add_error(line, str(e))
            continue

        status = _STATUS_ALIASES.get(row.get("status", "").lower(), GradeStatus.IN_PROGRESS)

        grade = db.scalar(select(Grade).where(
            Grade.student_id == student.id,
            Grade.course_id == course.id,
            Grade.semester == row["semester"],
        ))
        if grade:
            before = _snapshot_before(grade, ("credits_earned", "score", "status"))
            grade.credits_earned = credits_earned
            grade.score = score
            grade.status = status
            result.updated += 1
            result.add_row(RowChange(line, "update", "grades", grade.id, before))
        else:
            new_grade = Grade(
                student_id=student.id,
                course_id=course.id,
                semester=row["semester"],
                credits_earned=credits_earned,
                score=score,
                status=status,
            )
            db.add(new_grade)
            db.flush()
            result.created += 1
            result.add_row(RowChange(line, "create", "grades", new_grade.id))
    return result


# ----- 统一入口：包事务 + 写批次记录 -----

IMPORTERS = {
    "students": import_students,
    "courses": import_courses,
    "programs": import_program,
    "grades": import_grades,
}


def run_import(
    db: Session,
    *,
    kind: str,
    df: pd.DataFrame,
    operator_id: int | None,
    filename: str,
    mapping: dict[str, str] | None = None,
    dry_run: bool = False,
) -> ImportBatch:
    """统一导入入口：执行 importer + 落 ImportBatch / ImportBatchRow。

    - dry_run=True：业务写入在 savepoint 内 rollback；批次记录在外层事务保留。
    - 非 dry_run：业务全部失败（且无成功）时整体 rollback，批次 status=rolled_back；
      其余情况 commit，status=completed。
    - mapping：{源列名: 目标字段} 字典；按映射重命名 df 后再执行 importer。
    """
    if kind not in IMPORTERS:
        raise ValueError(f"不支持的导入类型: {kind}")
    importer_fn = IMPORTERS[kind]
    if mapping:
        df = apply_mapping(df, mapping)
    total_rows = int(len(df.index)) if df is not None else 0
    log.info("import_start", kind=kind, filename=filename, total_rows=total_rows, dry_run=dry_run)

    result: ImportResult
    status_str: str

    if dry_run:
        # 嵌套事务（savepoint）：执行后 rollback，业务写入回退，外层事务仍可用
        sp = db.begin_nested()
        try:
            result = importer_fn(db, df)
        finally:
            sp.rollback()
        status_str = "dry_run"
    else:
        # 业务全错且无成功 → 整体回滚事务（与历史行为一致）
        sp = db.begin_nested()
        try:
            result = importer_fn(db, df)
            if result.errors and result.created == 0 and result.updated == 0:
                sp.rollback()
                status_str = "rolled_back"
            else:
                sp.commit()
                status_str = "completed"
        except Exception:
            sp.rollback()
            raise

    batch = ImportBatch(
        kind=kind,
        filename=filename,
        status=status_str,
        dry_run=dry_run,
        total_rows=total_rows,
        created_count=result.created,
        updated_count=result.updated,
        skipped_count=result.skipped,
        error_count=len(result.errors),
        errors=result.errors or None,
        mapping=mapping,
        operator_id=operator_id,
    )
    db.add(batch)
    db.flush()
    # 写行级快照（仅非 dry-run 且实际写入了的行；dry_run 也记录便于预检参考）
    for rc in result.rows:
        db.add(ImportBatchRow(
            batch_id=batch.id,
            row_no=rc.row_no,
            op=rc.op,
            table_name=rc.table_name,
            record_pk=rc.record_pk,
            before=rc.before,
        ))
    log.info(
        "import_finish", kind=kind, filename=filename, status=status_str,
        created=result.created, updated=result.updated, error_count=len(result.errors),
    )
    return batch
