"""预警引擎。

根据学生当前所处阶段（已入学的学期数）与培养方案完成度，生成分级预警：

- ``severe``  严重：必修类完成度 < 50%，或总缺口 / 总要求 > 50%，或存在挂科未重修
- ``warn``    警告：总缺口 / 总要求 > 25%，或某分类完成度 < 70%
- ``info``    提示：存在任意缺口 > 0

阶段进度估算（粗略）：
- 每学年按 2 学期计，当前学期序号 = (current_year - enroll_year) * 2 + (1 if month <= 6 else 2)
- 期望完成比例 = min(stage / 8, 1.0)  （按 4 年制 8 学期）

实际部署时可通过 ``rule`` 参数覆盖阈值。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.student import Student
from app.models.warning import Warning, WarningLevel
from app.models.warning_rule import WarningRuleORM
from app.services.credit_compare import ProgressReport, compute_student_progress


@dataclass
class WarningRule:
    severe_total_gap_ratio: float = 0.5
    warn_total_gap_ratio: float = 0.25
    severe_required_ratio: float = 0.5
    warn_category_ratio: float = 0.7
    required_category_keywords: tuple[str, ...] = ("必修",)
    stage_total_semesters: int = 8


DEFAULT_RULE = WarningRule()


def _from_orm(orm: WarningRuleORM) -> WarningRule:
    return WarningRule(
        severe_total_gap_ratio=orm.severe_total_gap_ratio,
        warn_total_gap_ratio=orm.warn_total_gap_ratio,
        severe_required_ratio=orm.severe_required_ratio,
        warn_category_ratio=orm.warn_category_ratio,
        required_category_keywords=tuple(orm.required_category_keywords or ["必修"]),
        stage_total_semesters=orm.stage_total_semesters,
    )


def load_rule_for_student(db: Session, student: Student) -> tuple[WarningRule, int | None]:
    """按 scope 选择适用规则：major 精确 > college 精确 > 全局；priority 高者优先。
    返回 (规则数据类, 命中规则 id)；DB 无任何规则则返回 (DEFAULT_RULE, None)。"""
    candidates = list(db.scalars(
        select(WarningRuleORM)
        .where(WarningRuleORM.enabled.is_(True))
        .order_by(WarningRuleORM.priority.desc(), WarningRuleORM.id.asc())
    ))
    if not candidates:
        return DEFAULT_RULE, None

    def score(r: WarningRuleORM) -> int:
        # major 精确匹配 > college 精确匹配 > 全局
        if r.scope_major and student.major and r.scope_major == student.major:
            return 3
        if r.scope_college and student.college and r.scope_college == student.college:
            return 2
        if not r.scope_major and not r.scope_college:
            return 1
        return 0  # 作用域不匹配，剔除

    matched = [(score(r), r) for r in candidates if score(r) > 0]
    if not matched:
        return DEFAULT_RULE, None
    # 先按匹配精度（major>college>global）降序，再保持 priority 顺序
    matched.sort(key=lambda x: x[0], reverse=True)
    best = matched[0][1]
    return _from_orm(best), best.id


def current_semester_label(now: datetime | None = None) -> str:
    now = now or datetime.now()
    term = 1 if now.month <= 6 else 2
    year = now.year if term == 2 else now.year - 1
    return f"{year}-{term}"


def estimated_stage(enroll_year: int, now: datetime | None = None) -> int:
    now = now or datetime.now()
    term = 1 if now.month <= 6 else 2
    years = max(now.year - enroll_year, 0)
    return min(max(years * 2 + (1 if term == 1 else 2), 1), DEFAULT_RULE.stage_total_semesters)


def _evaluate(report: ProgressReport, stage: int, rule: WarningRule) -> tuple[str, str, dict] | None:
    if report.total_required <= 0:
        return None

    expected_ratio = min(stage / rule.stage_total_semesters, 1.0)
    total_done_ratio = float((report.total_earned + report.total_in_progress) / report.total_required)
    gap_ratio = 1 - total_done_ratio

    # 必修类缺口
    required_buckets = [
        b for b in report.buckets
        if any(k in b.category for k in rule.required_category_keywords) and b.required > 0
    ]
    worst_required_ratio = min(
        (float((b.earned + b.in_progress) / b.required) for b in required_buckets),
        default=1.0,
    )

    has_failed = bool(report.failed_courses)

    detail = {
        "stage": stage,
        "expected_completion_ratio": round(expected_ratio, 4),
        "actual_completion_ratio": round(total_done_ratio, 4),
        "total_gap": str(report.total_gap),
        "total_required": str(report.total_required),
        "buckets": [
            {
                "category": b.category,
                "required": str(b.required),
                "earned": str(b.earned),
                "in_progress": str(b.in_progress),
                "gap": str(b.gap),
            }
            for b in report.buckets if b.required > 0
        ],
        "failed_count": len(report.failed_courses),
    }

    # 严重
    if (
        has_failed
        or worst_required_ratio < rule.severe_required_ratio
        or (gap_ratio > rule.severe_total_gap_ratio and expected_ratio > 0.5)
    ):
        reasons = []
        if has_failed:
            reasons.append(f"存在 {len(report.failed_courses)} 门挂科未通过")
        if worst_required_ratio < rule.severe_required_ratio:
            reasons.append("必修类完成度严重不足")
        if gap_ratio > rule.severe_total_gap_ratio and expected_ratio > 0.5:
            reasons.append("总学分缺口过大")
        return WarningLevel.SEVERE.value, "学业严重预警：" + "；".join(reasons), detail

    # 警告
    worst_any_ratio = min(
        (float((b.earned + b.in_progress) / b.required) for b in report.buckets if b.required > 0),
        default=1.0,
    )
    if gap_ratio > rule.warn_total_gap_ratio or worst_any_ratio < rule.warn_category_ratio:
        return WarningLevel.WARN.value, "学业进度落后，需关注分类学分完成情况", detail

    # 提示
    if report.total_gap > 0:
        return WarningLevel.INFO.value, "存在学分缺口，建议尽早规划补修", detail

    return None


def generate_for_student(
    db: Session,
    student: Student,
    *,
    semester: str | None = None,
    rule: WarningRule | None = None,
    persist: bool = True,
) -> Warning | None:
    rule_id: int | None = None
    if rule is None:
        rule, rule_id = load_rule_for_student(db, student)
    report = compute_student_progress(db, student)
    stage = estimated_stage(student.enroll_year)
    outcome = _evaluate(report, stage, rule)
    if not outcome:
        return None
    level, summary, detail = outcome
    if rule_id is not None:
        detail["rule_id"] = rule_id
    semester = semester or current_semester_label()

    warning = Warning(
        student_id=student.id,
        level=level,
        semester=semester,
        summary=summary,
        detail=detail,
    )
    if persist:
        db.add(warning)
        db.flush()
    return warning


def generate_batch(
    db: Session,
    students: Iterable[Student],
    *,
    semester: str | None = None,
    rule: WarningRule | None = None,
) -> dict:
    semester = semester or current_semester_label()
    created = 0
    counts = {WarningLevel.INFO.value: 0, WarningLevel.WARN.value: 0, WarningLevel.SEVERE.value: 0}
    for s in students:
        w = generate_for_student(db, s, semester=semester, rule=rule)
        if w:
            created += 1
            counts[w.level] += 1
    db.commit()
    return {"semester": semester, "created": created, "by_level": counts}
