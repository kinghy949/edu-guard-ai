"""教务数据批量导入。

- 入口接受 ``bytes`` + 文件后缀，自动用 pandas 解析为 DataFrame。
- 每个 ``import_*`` 函数返回 ``ImportResult``：created/updated/skipped/errors。
- 所有写入在同一事务中执行，整体失败回滚。
"""
from __future__ import annotations

import io
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.course import Course
from app.models.grade import Grade, GradeStatus
from app.models.program import CreditBucket, Program, ProgramCourse
from app.models.student import Student
from app.models.user import User, UserRole


@dataclass
class ImportResult:
    created: int = 0
    updated: int = 0
    skipped: int = 0
    errors: list[dict[str, Any]] = field(default_factory=list)

    def add_error(self, row: int, message: str) -> None:
        self.errors.append({"row": row, "message": message})


def parse_table(content: bytes, filename: str) -> pd.DataFrame:
    """根据文件后缀解析为 DataFrame。"""
    name = filename.lower()
    buf = io.BytesIO(content)
    if name.endswith(".csv"):
        return pd.read_csv(buf, dtype=str, keep_default_na=False)
    if name.endswith((".xlsx", ".xls")):
        return pd.read_excel(buf, dtype=str, keep_default_na=False)
    raise ValueError("仅支持 .csv / .xlsx / .xls")


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
            student.name = row["name"]
            student.gender = row.get("gender") or None
            student.college = row["college"]
            student.major = row["major"]
            student.class_name = row.get("class_name") or None
            result.updated += 1
            continue

        user = User(
            username=row["student_no"],
            password_hash=hash_password(row["student_no"]),
            role=default_role,
            email=row.get("email") or None,
            phone=row.get("phone") or None,
            display_name=row["name"],
        )
        db.add(user)
        db.flush()
        db.add(Student(
            user_id=user.id,
            student_no=row["student_no"],
            name=row["name"],
            gender=row.get("gender") or None,
            enroll_year=enroll_year,
            college=row["college"],
            major=row["major"],
            class_name=row.get("class_name") or None,
        ))
        result.created += 1
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
            course.name = row["name"]
            course.credits = credits
            course.hours = hours
            course.category_default = row.get("category_default") or None
            course.description = row.get("description") or None
            result.updated += 1
        else:
            db.add(Course(
                code=row["code"],
                name=row["name"],
                credits=credits,
                hours=hours,
                category_default=row.get("category_default") or None,
                description=row.get("description") or None,
            ))
            result.created += 1
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
            pc.bucket_id = bucket.id
            pc.is_required = is_required
            pc.semester_suggested = sem
            result.updated += 1
        else:
            db.add(ProgramCourse(
                program_id=program.id,
                course_id=course.id,
                bucket_id=bucket.id,
                is_required=is_required,
                semester_suggested=sem,
            ))
            result.created += 1
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
            grade.credits_earned = credits_earned
            grade.score = score
            grade.status = status
            result.updated += 1
        else:
            db.add(Grade(
                student_id=student.id,
                course_id=course.id,
                semester=row["semester"],
                credits_earned=credits_earned,
                score=score,
                status=status,
            ))
            result.created += 1
    return result
