"""演示数据种子（扩展版）。

构造：
- 3 个培养方案：计算机科学与技术（CS）/ 软件工程（SE）/ 网络工程（NE），同套公共底盘但专业方向不同
- 约 80 门课程（含三个方向的专业必修与选修）
- 25 名学生，覆盖 2021-2024 入学年份，多种完成度场景
- 一名辅导员账户
- 自动批量生成预警，并随机将 ~35% 标记为已处理
- 为每条预警写入站内通知记录（含部分已读）
- 注入 3 段示例 AI 学业问答会话

幂等：再次运行只补全缺失项，不重复创建。

用法（容器内）：
    docker compose -f docker-compose.prod.yml exec backend python -m scripts.seed_demo
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select

from app.core.db import SessionLocal
from app.core.security import hash_password
from app.models.chat import ChatMessage, ChatSession
from app.models.course import Course
from app.models.grade import Grade, GradeStatus
from app.models.notification import (
    Notification, NotificationChannel, NotificationStatus,
)
from app.models.program import CreditBucket, Program, ProgramCourse
from app.models.student import Student
from app.models.user import User, UserRole
from app.models.warning import Warning, WarningLevel
from app.services.warning_engine import generate_for_student

random.seed(42)


# ============================================================================
# 1. 培养方案与学分桶
# ============================================================================

PROGRAMS = [
    {
        "code": "CS-2022", "name": "计算机科学与技术（2022 版）",
        "college": "信息与计算机科学学院", "major": "计算机科学与技术",
        "version": "2022", "total_credits": Decimal("160"),
    },
    {
        "code": "SE-2022", "name": "软件工程（2022 版）",
        "college": "信息与计算机科学学院", "major": "软件工程",
        "version": "2022", "total_credits": Decimal("162"),
    },
    {
        "code": "NE-2022", "name": "网络工程（2022 版）",
        "college": "信息与计算机科学学院", "major": "网络工程",
        "version": "2022", "total_credits": Decimal("160"),
    },
]

BUCKETS_TPL = [
    ("公共必修", Decimal("48")),
    ("学科基础", Decimal("32")),
    ("专业必修", Decimal("40")),
    ("专业选修", Decimal("20")),
    ("通识教育", Decimal("10")),
    ("实践创新", Decimal("10")),
]

# ============================================================================
# 2. 课程（公共底盘 + 三方向）
# ============================================================================

# (code, name, credits, category, sem)
COMMON_COURSES: list[tuple[str, str, str, str, int]] = [
    # 公共必修 ~48
    ("GEN101", "思想道德与法治", "3", "公共必修", 1),
    ("GEN102", "中国近现代史纲要", "3", "公共必修", 2),
    ("GEN103", "马克思主义基本原理", "3", "公共必修", 3),
    ("GEN104", "毛泽东思想和中国特色社会主义理论体系概论", "3", "公共必修", 4),
    ("GEN105", "形势与政策", "2", "公共必修", 1),
    ("ENG101", "大学英语（一）", "4", "公共必修", 1),
    ("ENG102", "大学英语（二）", "4", "公共必修", 2),
    ("ENG103", "大学英语（三）", "4", "公共必修", 3),
    ("ENG104", "大学英语（四）", "4", "公共必修", 4),
    ("PE101", "体育（一）", "1", "公共必修", 1),
    ("PE102", "体育（二）", "1", "公共必修", 2),
    ("PE103", "体育（三）", "1", "公共必修", 3),
    ("PE104", "体育（四）", "1", "公共必修", 4),
    ("MIL101", "军事理论", "2", "公共必修", 1),
    ("CAR101", "大学生职业生涯规划", "1", "公共必修", 1),
    ("CAR102", "就业指导", "1", "公共必修", 6),
    ("PSY101", "心理健康教育", "2", "公共必修", 2),
    ("PHY101", "大学物理", "4", "公共必修", 2),
    ("PHY102", "大学物理实验", "2", "公共必修", 3),
    ("CS100", "计算机导论", "2", "公共必修", 1),
    # 学科基础 ~32
    ("MATH101", "高等数学（一）", "5", "学科基础", 1),
    ("MATH102", "高等数学（二）", "5", "学科基础", 2),
    ("MATH201", "线性代数", "4", "学科基础", 2),
    ("MATH202", "概率论与数理统计", "4", "学科基础", 3),
    ("MATH203", "离散数学", "4", "学科基础", 3),
    ("CS201", "C 语言程序设计", "4", "学科基础", 1),
    ("CS202", "数据结构", "4", "学科基础", 2),
    ("CS203", "面向对象程序设计（Java）", "3", "学科基础", 3),
    ("CS204", "数字逻辑", "3", "学科基础", 3),
    # 通识 ~10
    ("HUM201", "中国传统文化", "2", "通识教育", 2),
    ("HUM202", "艺术鉴赏", "2", "通识教育", 3),
    ("HUM203", "科技伦理与社会", "2", "通识教育", 4),
    ("HUM204", "经济学原理", "2", "通识教育", 5),
    ("HUM205", "创业基础", "2", "通识教育", 6),
    # 实践 ~10
    ("PRA301", "数据结构课程设计", "2", "实践创新", 3),
    ("PRA302", "操作系统课程设计", "2", "实践创新", 5),
    ("PRA303", "数据库课程设计", "2", "实践创新", 5),
    ("PRA304", "专业实习", "2", "实践创新", 7),
    ("PRA305", "毕业设计", "2", "实践创新", 8),
]

# 专业必修/选修 按方向
PROFESSIONAL_COURSES: dict[str, list[tuple[str, str, str, str, int]]] = {
    "CS-2022": [
        # 专业必修 ~40
        ("CS301", "计算机组成原理", "4", "专业必修", 4),
        ("CS302", "操作系统", "4", "专业必修", 4),
        ("CS303", "计算机网络", "4", "专业必修", 5),
        ("CS304", "数据库系统原理", "4", "专业必修", 4),
        ("CS305", "编译原理", "3", "专业必修", 5),
        ("CS306", "软件工程", "3", "专业必修", 5),
        ("CS307", "算法设计与分析", "3", "专业必修", 4),
        ("CS308", "计算机系统结构", "3", "专业必修", 6),
        ("CS309", "人工智能导论", "3", "专业必修", 5),
        ("CS310", "信息安全基础", "3", "专业必修", 6),
        ("CS311", "Web 应用开发", "3", "专业必修", 5),
        ("CS312", "大数据技术", "3", "专业必修", 6),
        # 专业选修 ~20
        ("CS401", "机器学习", "3", "专业选修", 6),
        ("CS402", "深度学习", "3", "专业选修", 7),
        ("CS403", "分布式系统", "3", "专业选修", 6),
        ("CS404", "云计算", "3", "专业选修", 7),
        ("CS405", "移动应用开发", "3", "专业选修", 6),
        ("CS406", "区块链技术", "2", "专业选修", 7),
        ("CS407", "计算机图形学", "3", "专业选修", 6),
        ("CS408", "自然语言处理", "3", "专业选修", 7),
    ],
    "SE-2022": [
        # 专业必修 ~40
        ("SE301", "软件需求工程", "3", "专业必修", 4),
        ("SE302", "软件体系结构", "3", "专业必修", 5),
        ("SE303", "软件设计模式", "3", "专业必修", 5),
        ("SE304", "软件测试技术", "3", "专业必修", 5),
        ("SE305", "软件项目管理", "3", "专业必修", 6),
        ("SE306", "软件质量保证", "3", "专业必修", 6),
        ("SE307", "数据库系统原理", "4", "专业必修", 4),
        ("SE308", "操作系统", "4", "专业必修", 4),
        ("SE309", "计算机网络", "4", "专业必修", 5),
        ("SE310", "算法设计与分析", "3", "专业必修", 4),
        ("SE311", "Web 全栈开发", "4", "专业必修", 5),
        ("SE312", "敏捷开发实践", "3", "专业必修", 6),
        # 专业选修 ~20
        ("SE401", "DevOps 与持续集成", "3", "专业选修", 6),
        ("SE402", "云原生应用开发", "3", "专业选修", 7),
        ("SE403", "微服务架构", "3", "专业选修", 7),
        ("SE404", "前端工程化实践", "3", "专业选修", 6),
        ("SE405", "性能调优", "2", "专业选修", 7),
        ("SE406", "iOS 应用开发", "3", "专业选修", 6),
        ("SE407", "Android 应用开发", "3", "专业选修", 6),
    ],
    "NE-2022": [
        # 专业必修 ~40
        ("NE301", "数据通信原理", "4", "专业必修", 4),
        ("NE302", "网络协议分析", "3", "专业必修", 4),
        ("NE303", "路由与交换技术", "4", "专业必修", 5),
        ("NE304", "网络规划与设计", "3", "专业必修", 5),
        ("NE305", "无线网络技术", "3", "专业必修", 6),
        ("NE306", "网络安全", "4", "专业必修", 5),
        ("NE307", "操作系统", "4", "专业必修", 4),
        ("NE308", "Linux 系统管理", "3", "专业必修", 4),
        ("NE309", "网络编程", "3", "专业必修", 5),
        ("NE310", "数据库系统原理", "4", "专业必修", 4),
        ("NE311", "云计算基础", "3", "专业必修", 6),
        ("NE312", "网络运维", "2", "专业必修", 6),
        # 专业选修 ~20
        ("NE401", "渗透测试", "3", "专业选修", 7),
        ("NE402", "SDN 与网络虚拟化", "3", "专业选修", 7),
        ("NE403", "物联网技术", "3", "专业选修", 6),
        ("NE404", "5G 通信", "3", "专业选修", 7),
        ("NE405", "区块链与加密", "2", "专业选修", 7),
        ("NE406", "密码学", "3", "专业选修", 6),
        ("NE407", "网络数据分析", "3", "专业选修", 6),
    ],
}

# ============================================================================
# 3. 学生（25 人，分布在 3 个专业、4 个年级）
# ============================================================================

# (student_no, name, gender, enroll_year, program_code, class_name, scenario)
STUDENTS = [
    # CS 2021 级（大四） — 临近毕业
    ("20210101", "刘洋", "男", 2021, "CS-2022", "计科 2101", "severe_failed"),
    ("20210102", "陈志强", "男", 2021, "CS-2022", "计科 2101", "severe_lag"),
    ("20210103", "周静怡", "女", 2021, "CS-2022", "计科 2102", "near_done"),
    ("20210104", "吴俊辉", "男", 2021, "CS-2022", "计科 2102", "near_done"),

    # CS 2022 级（大三下）
    ("20220201", "张伟", "男", 2022, "CS-2022", "计科 2201", "severe_lag"),
    ("20220202", "李娜", "女", 2022, "CS-2022", "计科 2201", "info_normal"),
    ("20220203", "王芳", "女", 2022, "CS-2022", "计科 2202", "info_normal"),
    ("20220204", "赵小明", "男", 2022, "CS-2022", "计科 2202", "warn_lag"),
    ("20220205", "孙雪儿", "女", 2022, "CS-2022", "计科 2203", "warn_lag"),
    ("20220206", "钱晨曦", "男", 2022, "CS-2022", "计科 2203", "info_normal"),

    # CS 2023 级（大二下）
    ("20230301", "黄思远", "男", 2023, "CS-2022", "计科 2301", "clean"),
    ("20230302", "周敏", "女", 2023, "CS-2022", "计科 2301", "clean"),
    ("20230303", "徐浩然", "男", 2023, "CS-2022", "计科 2302", "warn_lag"),

    # CS 2024 级（大一下）
    ("20240401", "马一鸣", "男", 2024, "CS-2022", "计科 2401", "freshman"),
    ("20240402", "高诗涵", "女", 2024, "CS-2022", "计科 2401", "freshman"),

    # SE 2022 级
    ("20220501", "韩立诚", "男", 2022, "SE-2022", "软工 2201", "info_normal"),
    ("20220502", "罗婉清", "女", 2022, "SE-2022", "软工 2201", "warn_lag"),
    ("20220503", "宋天宇", "男", 2022, "SE-2022", "软工 2202", "near_done"),

    # SE 2023 级
    ("20230601", "白雨萱", "女", 2023, "SE-2022", "软工 2301", "clean"),
    ("20230602", "唐毅恒", "男", 2023, "SE-2022", "软工 2301", "warn_lag"),

    # NE 2022 级
    ("20220701", "顾明轩", "男", 2022, "NE-2022", "网工 2201", "severe_lag"),
    ("20220702", "邓佳琦", "女", 2022, "NE-2022", "网工 2201", "info_normal"),

    # NE 2023 级
    ("20230801", "薛清扬", "男", 2023, "NE-2022", "网工 2301", "clean"),
    ("20230802", "范婉婷", "女", 2023, "NE-2022", "网工 2301", "warn_lag"),

    # NE 2024 级
    ("20240901", "陆思辰", "男", 2024, "NE-2022", "网工 2401", "freshman"),
]


# ============================================================================
# 辅助
# ============================================================================

def upsert_program(db, spec: dict) -> Program:
    program = db.scalar(select(Program).where(Program.code == spec["code"]))
    if not program:
        program = Program(
            code=spec["code"], name=spec["name"], college=spec["college"],
            major=spec["major"], version=spec["version"],
            total_credits_required=spec["total_credits"],
        )
        db.add(program)
        db.flush()
    return program


def upsert_buckets(db, program: Program) -> dict[str, int]:
    out = {}
    for cat, req in BUCKETS_TPL:
        b = db.scalar(select(CreditBucket).where(
            CreditBucket.program_id == program.id, CreditBucket.category == cat))
        if not b:
            b = CreditBucket(program_id=program.id, category=cat, credits_required=req)
            db.add(b)
            db.flush()
        out[cat] = b.id
    return out


def upsert_course(db, code: str, name: str, credits: str, cat: str) -> Course:
    c = db.scalar(select(Course).where(Course.code == code))
    if not c:
        c = Course(code=code, name=name, credits=Decimal(credits), category_default=cat)
        db.add(c)
        db.flush()
    return c


def upsert_program_course(db, program: Program, course: Course, bucket_id: int, sem: int):
    pc = db.scalar(select(ProgramCourse).where(
        ProgramCourse.program_id == program.id, ProgramCourse.course_id == course.id))
    if not pc:
        # 公共底盘、学科基础按 cat 判定必修；专业必修/选修按 category 判断
        is_required = course.category_default in ("公共必修", "学科基础", "专业必修", "实践创新")
        db.add(ProgramCourse(
            program_id=program.id, course_id=course.id, bucket_id=bucket_id,
            is_required=is_required, semester_suggested=sem,
        ))
        db.flush()


def seed_programs(db) -> dict[str, tuple[int, dict[str, int], list[tuple]]]:
    """returns code -> (program_id, bucket_ids, course list)"""
    out = {}
    for spec in PROGRAMS:
        program = upsert_program(db, spec)
        buckets = upsert_buckets(db, program)
        course_list = list(COMMON_COURSES) + list(PROFESSIONAL_COURSES[spec["code"]])
        for code, name, credits, cat, sem in course_list:
            course = upsert_course(db, code, name, credits, cat)
            upsert_program_course(db, program, course, buckets[cat], sem)
        out[spec["code"]] = (program.id, buckets, course_list)
    return out


def upsert_user(db, username, password, role, name, email=None, phone=None):
    u = db.scalar(select(User).where(User.username == username))
    if u:
        return u
    u = User(
        username=username, password_hash=hash_password(password),
        role=role, display_name=name, email=email, phone=phone,
    )
    db.add(u)
    db.flush()
    return u


def upsert_student(db, no, name, gender, year, program_id, class_name):
    user = upsert_user(
        db, no, no, UserRole.STUDENT, name,
        email=f"{no}@stu.example.edu.cn", phone=f"139{no[-8:]}",
    )
    s = db.scalar(select(Student).where(Student.student_no == no))
    if s:
        return s
    s = Student(
        user_id=user.id, student_no=no, name=name, gender=gender,
        enroll_year=year,
        college="信息与计算机科学学院",
        major={"CS-2022": "计算机科学与技术", "SE-2022": "软件工程", "NE-2022": "网络工程"}[
            {1: "CS-2022", 2: "SE-2022", 3: "NE-2022"}.get(0, "CS-2022")  # placeholder, overridden
        ],
        class_name=class_name, program_id=program_id,
    )
    db.add(s)
    db.flush()
    return s


def upsert_student_with_program_code(db, no, name, gender, year, program_id, program_code, class_name):
    user = upsert_user(
        db, no, no, UserRole.STUDENT, name,
        email=f"{no}@stu.example.edu.cn", phone=f"139{no[-8:]}",
    )
    s = db.scalar(select(Student).where(Student.student_no == no))
    if s:
        return s
    major = {"CS-2022": "计算机科学与技术", "SE-2022": "软件工程", "NE-2022": "网络工程"}[program_code]
    s = Student(
        user_id=user.id, student_no=no, name=name, gender=gender,
        enroll_year=year, college="信息与计算机科学学院", major=major,
        class_name=class_name, program_id=program_id,
    )
    db.add(s)
    db.flush()
    return s


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


def sem_label(student: Student, stage: int) -> str:
    year = student.enroll_year + (stage - 1) // 2
    term = 1 if stage % 2 == 1 else 2
    return f"{year}-{term}"


def seed_grades(db, student: Student, course_list, scenario: str, course_id_by_code: dict[str, int]):
    """根据 scenario 与学生入学年份生成成绩。"""
    ordered = sorted(course_list, key=lambda x: (x[4], x[0]))  # by sem, code

    def s(stage: int) -> str:
        return sem_label(student, stage)

    def base_score(code: str) -> int:
        return 70 + (hash(code) % 22)

    if scenario == "severe_failed":
        # 大四：前 6 学期常规进度，2 门挂科 + 漏修一些专业课
        fail_codes = ("CS302", "CS305", "SE304", "NE306", "PRA302")
        for code, name, credits, cat, sem in ordered:
            if sem > 6:
                continue
            if code in fail_codes:
                add_grade(db, student, course_id_by_code[code], credits, GradeStatus.FAILED,
                          s(sem), score=42 + (hash(code) % 8))
            elif sem <= 6 and random.random() > 0.05:  # 5% 漏修
                add_grade(db, student, course_id_by_code[code], credits, GradeStatus.COMPLETED,
                          s(sem), score=base_score(code))

    elif scenario == "severe_lag":
        # 大三末：前 4 学期完成，第 5 学期 only in_progress 少量
        for code, name, credits, cat, sem in ordered:
            if sem <= 4 and random.random() > 0.08:
                add_grade(db, student, course_id_by_code[code], credits, GradeStatus.COMPLETED,
                          s(sem), score=base_score(code))
            elif sem == 5 and code in ("CS303", "CS305", "SE302", "SE304", "NE303", "NE306"):
                add_grade(db, student, course_id_by_code[code], credits, GradeStatus.IN_PROGRESS, s(5))

    elif scenario == "warn_lag":
        # 大三末：前 5 学期完成 80%，部分高学期课没修
        for code, name, credits, cat, sem in ordered:
            if sem <= 5 and random.random() > 0.18:
                add_grade(db, student, course_id_by_code[code], credits, GradeStatus.COMPLETED,
                          s(sem), score=base_score(code))
            elif sem == 6 and random.random() > 0.5:
                add_grade(db, student, course_id_by_code[code], credits, GradeStatus.IN_PROGRESS, s(6))

    elif scenario == "info_normal":
        # 大三末：前 5 学期按推荐学期完成，第 6 学期在修
        for code, name, credits, cat, sem in ordered:
            if sem <= 5:
                add_grade(db, student, course_id_by_code[code], credits, GradeStatus.COMPLETED,
                          s(sem), score=78 + (hash(code) % 16))
            elif sem == 6:
                add_grade(db, student, course_id_by_code[code], credits, GradeStatus.IN_PROGRESS, s(6))

    elif scenario == "near_done":
        # 大四：前 7 学期完成，第 8 学期在修毕业设计
        for code, name, credits, cat, sem in ordered:
            if sem <= 7 and random.random() > 0.03:
                add_grade(db, student, course_id_by_code[code], credits, GradeStatus.COMPLETED,
                          s(sem), score=78 + (hash(code) % 18))
            elif sem == 8:
                add_grade(db, student, course_id_by_code[code], credits, GradeStatus.IN_PROGRESS, s(8))

    elif scenario == "clean":
        # 大二下：前 4 学期按部就班，第 5 学期在修
        for code, name, credits, cat, sem in ordered:
            if sem <= 4:
                add_grade(db, student, course_id_by_code[code], credits, GradeStatus.COMPLETED,
                          s(sem), score=82 + (hash(code) % 15))
            elif sem == 5:
                add_grade(db, student, course_id_by_code[code], credits, GradeStatus.IN_PROGRESS, s(5))

    elif scenario == "freshman":
        # 大一下：第 1 学期完成，第 2 学期在修
        for code, name, credits, cat, sem in ordered:
            if sem == 1:
                add_grade(db, student, course_id_by_code[code], credits, GradeStatus.COMPLETED,
                          s(1), score=80 + (hash(code) % 18))
            elif sem == 2:
                add_grade(db, student, course_id_by_code[code], credits, GradeStatus.IN_PROGRESS, s(2))


# ============================================================================
# 4. AI 会话样例
# ============================================================================

CHAT_SAMPLES = [
    {
        "title": "我还差多少学分？",
        "messages": [
            ("user", "你好，能帮我看看我现在还差多少学分吗？"),
            ("assistant", "你好！根据你的培养方案，目前还有约 32 学分待完成，主要集中在专业选修（缺口 14 学分）和实践创新（缺口 8 学分）。建议下学期重点选修《机器学习》《分布式系统》。"),
            ("user", "那毕业设计需要单独申请吗？"),
            ("assistant", "毕业设计（PRA305，2 学分）由学院在第 8 学期统一开课并分配指导老师，不需要单独申请。提前与学院公布的指导教师名单沟通选题即可。"),
        ],
    },
    {
        "title": "下学期选课建议",
        "messages": [
            ("user", "我下学期应该选哪些课？想优先完成专业必修。"),
            ("assistant", "结合你当前的完成情况，建议下学期优先选：\n1. 编译原理（CS305，3 学分，必修）\n2. 软件工程（CS306，3 学分，必修）\n3. 人工智能导论（CS309，3 学分，必修）\n如有余力可加选《Web 应用开发》。"),
        ],
    },
    {
        "title": "挂科了怎么办",
        "messages": [
            ("user", "我操作系统挂科了，会影响毕业吗？"),
            ("assistant", "操作系统是专业必修，必须重修通过才能毕业。建议在下学期或暑期开课时尽快报名重修，避免拖到大四影响毕业设计安排。重修通过后挂科记录会保留但不影响毕业资格。"),
        ],
    },
]


# ============================================================================
# 主流程
# ============================================================================

def main():
    with SessionLocal() as db:
        # 1. 培养方案 + 课程
        programs = seed_programs(db)
        all_course_ids: dict[str, int] = {
            c.code: c.id for c in db.scalars(select(Course))
        }
        db.commit()
        print(f"✅ 培养方案 {len(programs)}，课程 {len(all_course_ids)}")

        # 2. 辅导员
        counselor = db.scalar(select(User).where(User.username == "counselor"))
        if not counselor:
            counselor = User(
                username="counselor", password_hash=hash_password("counselor123"),
                role=UserRole.COUNSELOR, display_name="辅导员-王老师",
                email="counselor@example.edu.cn", phone="13800000000",
            )
            db.add(counselor)
            db.commit()
            print("✅ 辅导员账户: counselor / counselor123")

        # 3. 学生 + 成绩
        student_count = 0
        for no, name, gender, year, prog_code, class_name, scenario in STUDENTS:
            program_id, _, course_list = programs[prog_code]
            student = upsert_student_with_program_code(db, no, name, gender, year, program_id, prog_code, class_name)
            seed_grades(db, student, course_list, scenario, all_course_ids)
            student_count += 1
        db.commit()
        print(f"✅ 学生 {student_count}（含成绩）")

        # 4. 预警：仅为还没生成过的学生生成
        warning_count = {"info": 0, "warn": 0, "severe": 0}
        new_warnings: list[Warning] = []
        for s in db.scalars(select(Student)):
            has = db.scalar(select(Warning).where(Warning.student_id == s.id).limit(1))
            if has:
                continue
            w = generate_for_student(db, s, semester="2026-1")
            if w:
                warning_count[w.level] += 1
                new_warnings.append(w)
        db.commit()

        # 5. 随机标记 ~35% 新预警已处理
        if new_warnings:
            resolved_n = max(1, int(len(new_warnings) * 0.35))
            for w in random.sample(new_warnings, resolved_n):
                w.resolved_at = datetime.now(timezone.utc) - timedelta(days=random.randint(1, 14))
                w.resolver_note = random.choice([
                    "已与学生当面沟通选课计划",
                    "学生承诺下学期重修",
                    "已联系任课教师协助",
                    "纳入下次班会重点关注名单",
                ])
            # 6. 通知记录（站内 + 邮件 70%）
            for w in new_warnings:
                student = db.get(Student, w.student_id)
                if not student:
                    continue
                db.add(Notification(
                    warning_id=w.id, user_id=student.user_id,
                    channel=NotificationChannel.INBOX, target=student.student_no,
                    status=NotificationStatus.SENT, sent_at=w.created_at,
                ))
                if random.random() < 0.7:
                    ok = random.random() < 0.9
                    db.add(Notification(
                        warning_id=w.id, user_id=student.user_id,
                        channel=NotificationChannel.EMAIL,
                        target=f"{student.student_no}@stu.example.edu.cn",
                        status=NotificationStatus.SENT if ok else NotificationStatus.FAILED,
                        error=None if ok else "SMTP timeout",
                        sent_at=w.created_at,
                    ))
            db.commit()
            print(f"✅ 新增预警: {warning_count}，已处理 {resolved_n} 条；通知记录已生成")
        else:
            print("ℹ️  所有学生已有预警记录，跳过生成")

        # 7. AI 会话样例（绑到第一个学生）
        first_student_user = db.scalar(
            select(User).join(Student, Student.user_id == User.id).order_by(Student.id).limit(1)
        )
        if first_student_user:
            existing = db.scalar(select(ChatSession).where(ChatSession.user_id == first_student_user.id))
            if not existing:
                for spec in CHAT_SAMPLES:
                    sess = ChatSession(user_id=first_student_user.id, title=spec["title"])
                    db.add(sess)
                    db.flush()
                    for role, content in spec["messages"]:
                        db.add(ChatMessage(session_id=sess.id, role=role, content=content))
                db.commit()
                print(f"✅ AI 会话样例: {len(CHAT_SAMPLES)} 条 (用户 {first_student_user.username})")

        print()
        print("=" * 60)
        print("登录账号速查")
        print("=" * 60)
        print(f"  管理员    admin       / admin123")
        print(f"  辅导员    counselor   / counselor123")
        print(f"  学生示例  20210101    / 20210101    (大四，挂科)")
        print(f"  学生示例  20220202    / 20220202    (大三，正常)")
        print(f"  学生示例  20230301    / 20230301    (大二，正常)")
        print(f"  全部学生密码 = 学号")


if __name__ == "__main__":
    main()
