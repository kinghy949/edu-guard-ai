"""演示数据种子。

用法（容器内）：
    docker compose -f docker-compose.prod.yml exec -T backend python -m scripts.seed_demo

构造一个"计算机科学与技术 2022 版"培养方案，配套 6 大学分桶 + 约 40 门课，
然后生成 4 名学生（不同入学年份 / 完成度状态），覆盖 严重 / 警告 / 提示 / 正常 四种典型场景。
"""
from __future__ import annotations

from decimal import Decimal
from typing import Iterable

from sqlalchemy import select

from app.core.db import SessionLocal
from app.core.security import hash_password
from app.models.course import Course
from app.models.grade import Grade, GradeStatus
from app.models.program import CreditBucket, Program, ProgramCourse
from app.models.student import Student
from app.models.user import User, UserRole


# ----- 1. 培养方案 -----

PROGRAM = {
    "code": "CS-2022",
    "name": "计算机科学与技术（2022 版）",
    "college": "计算机科学与技术学院",
    "major": "计算机科学与技术",
    "version": "2022",
    "total_credits": Decimal("160"),
}

# 各学分桶（分类 + 学分要求）
BUCKETS = [
    ("公共必修", Decimal("48")),
    ("学科基础", Decimal("32")),
    ("专业必修", Decimal("40")),
    ("专业选修", Decimal("20")),
    ("通识教育", Decimal("10")),
    ("实践创新", Decimal("10")),
]

# (code, name, credits, bucket_category, is_required, semester_suggested)
COURSES: list[tuple[str, str, str, str, bool, int]] = [
    # 公共必修
    ("GEN101", "思想道德与法治", "3", "公共必修", True, 1),
    ("GEN102", "中国近现代史纲要", "3", "公共必修", True, 2),
    ("GEN103", "马克思主义基本原理", "3", "公共必修", True, 3),
    ("GEN104", "毛泽东思想和中国特色社会主义理论体系概论", "3", "公共必修", True, 4),
    ("GEN105", "形势与政策", "2", "公共必修", True, 1),
    ("ENG101", "大学英语（一）", "4", "公共必修", True, 1),
    ("ENG102", "大学英语（二）", "4", "公共必修", True, 2),
    ("ENG103", "大学英语（三）", "4", "公共必修", True, 3),
    ("ENG104", "大学英语（四）", "4", "公共必修", True, 4),
    ("PE101", "体育（一）", "1", "公共必修", True, 1),
    ("PE102", "体育（二）", "1", "公共必修", True, 2),
    ("PE103", "体育（三）", "1", "公共必修", True, 3),
    ("PE104", "体育（四）", "1", "公共必修", True, 4),
    ("MIL101", "军事理论", "2", "公共必修", True, 1),
    ("CAR101", "大学生职业生涯规划", "1", "公共必修", True, 1),
    ("CAR102", "就业指导", "1", "公共必修", True, 6),
    ("PSY101", "心理健康教育", "2", "公共必修", True, 2),
    ("PHY101", "大学物理", "4", "公共必修", True, 2),
    ("PHY102", "大学物理实验", "2", "公共必修", True, 3),
    ("CS100", "计算机导论", "2", "公共必修", True, 1),

    # 学科基础
    ("MATH101", "高等数学（一）", "5", "学科基础", True, 1),
    ("MATH102", "高等数学（二）", "5", "学科基础", True, 2),
    ("MATH201", "线性代数", "4", "学科基础", True, 2),
    ("MATH202", "概率论与数理统计", "4", "学科基础", True, 3),
    ("MATH203", "离散数学", "4", "学科基础", True, 3),
    ("CS201", "C 语言程序设计", "4", "学科基础", True, 1),
    ("CS202", "数据结构", "4", "学科基础", True, 2),
    ("CS203", "面向对象程序设计（Java）", "3", "学科基础", True, 3),
    ("CS204", "数字逻辑", "3", "学科基础", True, 3),

    # 专业必修
    ("CS301", "计算机组成原理", "4", "专业必修", True, 4),
    ("CS302", "操作系统", "4", "专业必修", True, 4),
    ("CS303", "计算机网络", "4", "专业必修", True, 5),
    ("CS304", "数据库系统原理", "4", "专业必修", True, 4),
    ("CS305", "编译原理", "3", "专业必修", True, 5),
    ("CS306", "软件工程", "3", "专业必修", True, 5),
    ("CS307", "算法设计与分析", "3", "专业必修", True, 4),
    ("CS308", "计算机系统结构", "3", "专业必修", True, 6),
    ("CS309", "人工智能导论", "3", "专业必修", True, 5),
    ("CS310", "信息安全基础", "3", "专业必修", True, 6),
    ("CS311", "Web 应用开发", "3", "专业必修", True, 5),
    ("CS312", "大数据技术", "3", "专业必修", True, 6),

    # 专业选修
    ("CS401", "机器学习", "3", "专业选修", False, 6),
    ("CS402", "深度学习", "3", "专业选修", False, 7),
    ("CS403", "分布式系统", "3", "专业选修", False, 6),
    ("CS404", "云计算", "3", "专业选修", False, 7),
    ("CS405", "移动应用开发", "3", "专业选修", False, 6),
    ("CS406", "区块链技术", "2", "专业选修", False, 7),
    ("CS407", "计算机图形学", "3", "专业选修", False, 6),
    ("CS408", "自然语言处理", "3", "专业选修", False, 7),

    # 通识教育
    ("HUM201", "中国传统文化", "2", "通识教育", False, 2),
    ("HUM202", "艺术鉴赏", "2", "通识教育", False, 3),
    ("HUM203", "科技伦理与社会", "2", "通识教育", False, 4),
    ("HUM204", "经济学原理", "2", "通识教育", False, 5),
    ("HUM205", "创业基础", "2", "通识教育", False, 6),

    # 实践创新
    ("PRA301", "数据结构课程设计", "2", "实践创新", True, 3),
    ("PRA302", "操作系统课程设计", "2", "实践创新", True, 5),
    ("PRA303", "数据库课程设计", "2", "实践创新", True, 5),
    ("PRA304", "专业实习", "2", "实践创新", True, 7),
    ("PRA305", "毕业设计", "2", "实践创新", True, 8),
]


# ----- 2. 学生（4 个典型场景） -----

# (student_no, name, gender, enroll_year, class_name, password)
STUDENTS = [
    ("20210101", "刘洋", "男", 2021, "计科 2101", "刘洋123"),  # 大四下，挂科 → severe
    ("20220203", "张伟", "男", 2022, "计科 2202", "张伟123"),  # 大三下，进度落后 → severe/warn
    ("20220318", "李娜", "女", 2022, "计科 2203", "李娜123"),  # 大三下，按部就班 → info
    ("20240415", "王芳", "女", 2024, "计科 2404", "王芳123"),  # 大二下，正常 → 无预警
]


def _semester(stage: int) -> str:
    """学生第 N 学期对应的标签（粗略：奇数=春季 X-2，偶数=秋季 X-1）。"""
    # stage=1 -> 2022-1, 2 -> 2022-2, 3 -> 2023-1...
    return f"{2021 + (stage + 1) // 2}-{1 if stage % 2 == 1 else 2}"


def make_grade(student_no_year: int, stage: int) -> str:
    """通用学期生成：根据学生入学年份计算第 stage 学期的标签。"""
    year = student_no_year + (stage - 1) // 2
    term = 1 if stage % 2 == 1 else 2
    return f"{year}-{term}"


def seed_courses(db) -> tuple[dict[str, int], dict[str, int]]:
    """返回 (course_code → id, bucket_category → id)。"""
    program = db.scalar(select(Program).where(Program.code == PROGRAM["code"]))
    if not program:
        program = Program(
            code=PROGRAM["code"],
            name=PROGRAM["name"],
            college=PROGRAM["college"],
            major=PROGRAM["major"],
            version=PROGRAM["version"],
            total_credits_required=PROGRAM["total_credits"],
        )
        db.add(program)
        db.flush()

    bucket_ids: dict[str, int] = {}
    for cat, req in BUCKETS:
        b = db.scalar(select(CreditBucket).where(
            CreditBucket.program_id == program.id, CreditBucket.category == cat))
        if not b:
            b = CreditBucket(program_id=program.id, category=cat, credits_required=req)
            db.add(b)
            db.flush()
        bucket_ids[cat] = b.id

    course_ids: dict[str, int] = {}
    for code, name, credits, cat, is_required, sem in COURSES:
        c = db.scalar(select(Course).where(Course.code == code))
        if not c:
            c = Course(code=code, name=name, credits=Decimal(credits), category_default=cat)
            db.add(c)
            db.flush()
        course_ids[code] = c.id

        pc = db.scalar(select(ProgramCourse).where(
            ProgramCourse.program_id == program.id, ProgramCourse.course_id == c.id))
        if not pc:
            db.add(ProgramCourse(
                program_id=program.id, course_id=c.id, bucket_id=bucket_ids[cat],
                is_required=is_required, semester_suggested=sem,
            ))

    return course_ids, bucket_ids, program.id


def upsert_student(db, no, name, gender, year, class_name, password, program_id):
    user = db.scalar(select(User).where(User.username == no))
    if not user:
        user = User(
            username=no, password_hash=hash_password(password),
            role=UserRole.STUDENT, display_name=name,
            email=f"{no}@example.edu.cn",
            phone=f"1380000{no[-4:]}",
        )
        db.add(user)
        db.flush()
    student = db.scalar(select(Student).where(Student.student_no == no))
    if not student:
        student = Student(
            user_id=user.id, student_no=no, name=name, gender=gender,
            enroll_year=year, college=PROGRAM["college"], major=PROGRAM["major"],
            class_name=class_name, program_id=program_id,
        )
        db.add(student)
        db.flush()
    return student


def add_grade(db, student, course_id, credits, status, semester, score=None):
    g = db.scalar(select(Grade).where(
        Grade.student_id == student.id, Grade.course_id == course_id, Grade.semester == semester))
    if g:
        return
    db.add(Grade(
        student_id=student.id, course_id=course_id, semester=semester,
        credits_earned=Decimal(credits) if status == GradeStatus.COMPLETED else Decimal("0"),
        score=Decimal(score) if score is not None else None,
        status=status,
    ))


def seed_grades_for_student(db, student, scenario: str, course_ids):
    """根据剧本生成成绩。

    scenario:
      - severe_failed: 大四，关键专业课挂科，必修类完成度低
      - severe_lag:    大三末，整体落后
      - info_normal:   大三末，按部就班但缺一点
      - clean:         大二末，进度正常无预警
    """
    # 按建议学期排序的课程列表
    ordered = sorted(COURSES, key=lambda x: (x[5], x[0]))

    def sem_of(stage: int) -> str:
        return f"{student.enroll_year + (stage - 1) // 2}-{1 if stage % 2 == 1 else 2}"

    if scenario == "severe_failed":
        # 大四下：完成 6 个学期的常规进度，第 7 学期开始几门挂科 + 漏修必修
        for code, name, credits, cat, is_req, sem in ordered:
            if sem > 6:
                continue
            # 模拟若干门挂科：操作系统、编译原理
            if code in ("CS302", "CS305"):
                add_grade(db, student, course_ids[code], credits, GradeStatus.FAILED, sem_of(sem), score=42)
            else:
                add_grade(db, student, course_ids[code], credits, GradeStatus.COMPLETED, sem_of(sem),
                          score=72 + (hash(code) % 20))

    elif scenario == "severe_lag":
        # 大三下：仅完成前 4 个学期的核心课，第 5 学期开始大面积漏选
        for code, name, credits, cat, is_req, sem in ordered:
            if sem <= 4:
                add_grade(db, student, course_ids[code], credits, GradeStatus.COMPLETED, sem_of(sem),
                          score=70 + (hash(code) % 20))
            elif sem == 5 and code in ("CS303", "CS305"):
                add_grade(db, student, course_ids[code], credits, GradeStatus.IN_PROGRESS, sem_of(5))

    elif scenario == "info_normal":
        # 大三下：前 5 学期按推荐学期完成，第 6 学期在修若干门
        for code, name, credits, cat, is_req, sem in ordered:
            if sem <= 5:
                add_grade(db, student, course_ids[code], credits, GradeStatus.COMPLETED, sem_of(sem),
                          score=78 + (hash(code) % 18))
            elif sem == 6:
                add_grade(db, student, course_ids[code], credits, GradeStatus.IN_PROGRESS, sem_of(6))

    elif scenario == "clean":
        # 大二下：前 4 个学期按推荐学期完成，第 5 学期在修
        for code, name, credits, cat, is_req, sem in ordered:
            if sem <= 4:
                add_grade(db, student, course_ids[code], credits, GradeStatus.COMPLETED, sem_of(sem),
                          score=82 + (hash(code) % 15))
            elif sem == 5:
                add_grade(db, student, course_ids[code], credits, GradeStatus.IN_PROGRESS, sem_of(5))


SCENARIOS = {
    "20210101": "severe_failed",
    "20220203": "severe_lag",
    "20220318": "info_normal",
    "20240415": "clean",
}


def main():
    with SessionLocal() as db:
        course_ids, bucket_ids, program_id = seed_courses(db)
        for no, name, gender, year, class_name, password in STUDENTS:
            student = upsert_student(db, no, name, gender, year, class_name, password, program_id)
            seed_grades_for_student(db, student, SCENARIOS[no], course_ids)
        db.commit()
        print("✅ 演示数据已生成")
        print("  培养方案: 1 个")
        print(f"  学分桶  : {len(BUCKETS)}")
        print(f"  课程    : {len(COURSES)}")
        print(f"  学生    : {len(STUDENTS)}")
        print("  登录账号（用户名=学号，密码见 STUDENTS 列表）:")
        for no, name, _, year, _, password in STUDENTS:
            print(f"    {no}  {name}（{year} 级）  密码: {password}")


if __name__ == "__main__":
    main()
