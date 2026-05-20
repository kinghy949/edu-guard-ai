"""为 LLM 拼装学生学业上下文。"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.student import Student
from app.services.credit_compare import compute_student_progress


def build_student_context(db: Session, student: Student) -> str:
    """生成一段 markdown 文本，注入到 system 消息后部。"""
    r = compute_student_progress(db, student)
    lines: list[str] = []
    lines.append("## 学生上下文")
    lines.append(f"- 姓名：{r.student_name}  学号：{r.student_no}")
    if r.program_name:
        lines.append(f"- 培养方案：{r.program_name}")
    lines.append(f"- 总学分要求：{r.total_required}")
    lines.append(f"- 已修：{r.total_earned}  在修：{r.total_in_progress}  缺口：{r.total_gap}")
    lines.append("")
    lines.append("### 各分类完成情况")
    for b in r.buckets:
        if b.required <= 0 and b.earned == 0 and b.in_progress == 0:
            continue
        lines.append(
            f"- {b.category}：要求 {b.required}，已修 {b.earned}，在修 {b.in_progress}，缺口 {b.gap}"
        )

    rec_lines: list[str] = []
    for b in r.buckets:
        if not b.recommended:
            continue
        rec_lines.append(f"- 【{b.category}】缺口 {b.gap}：")
        for c in b.recommended:
            flag = "必修" if c.is_required else "选修"
            sem = f"建议第 {c.semester_suggested} 学期" if c.semester_suggested else ""
            rec_lines.append(f"  - {c.name}（{c.code}，{c.credits} 学分，{flag}）{sem}")
    if rec_lines:
        lines.append("")
        lines.append("### 推荐补修课（仅可从下列中推荐，禁止编造）")
        lines.extend(rec_lines)

    if r.failed_courses:
        lines.append("")
        lines.append("### 挂科未通过")
        for c in r.failed_courses:
            lines.append(f"- {c.name}（{c.code}，{c.credits} 学分）")

    return "\n".join(lines)
