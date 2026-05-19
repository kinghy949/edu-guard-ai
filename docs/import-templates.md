# 批量导入模板

> 支持 `.csv` / `.xlsx` / `.xls`，UTF-8。所有接口需 `counselor` 或 `admin` 角色。
> 接口路径：`POST /api/v1/imports/{students|courses|programs|grades}`，`multipart/form-data` 字段名 `file`。
> 列名说明可调用 `GET /api/v1/imports/templates`。

## 一、学生名册 `/imports/students`

| 列 | 必填 | 说明 |
| --- | --- | --- |
| student_no | ✓ | 学号；同时作为初始用户名与密码 |
| name | ✓ | 姓名 |
| enroll_year | ✓ | 入学年份，整数（如 2024） |
| college | ✓ | 学院 |
| major | ✓ | 专业 |
| class_name |  | 班级 |
| gender |  | 性别 |
| email |  | 邮箱 |
| phone |  | 手机号 |

> 已存在的学号会被**更新**（用户基本信息不动），新学号会创建 `User`（角色 `student`，初始密码 = 学号）。

## 二、课程主数据 `/imports/courses`

| 列 | 必填 | 说明 |
| --- | --- | --- |
| code | ✓ | 课程编码（唯一） |
| name | ✓ | 课程名称 |
| credits | ✓ | 学分（小数） |
| hours |  | 学时 |
| category_default |  | 默认分类 |
| description |  | 简介 |

## 三、培养方案 `/imports/programs`

**每行 = 一门课在某方案中的归属**。同一方案的多门课请使用多行，方案与学分桶字段会自动去重。

| 列 | 必填 | 说明 |
| --- | --- | --- |
| program_code | ✓ | 方案编码 |
| program_name | ✓ | 方案名称 |
| college | ✓ | 学院 |
| major | ✓ | 专业 |
| version | ✓ | 版本（如 2023） |
| total_credits | ✓ | 方案总学分 |
| category | ✓ | 学分类别（必修/限选/任选/通识/实践/创新创业 …） |
| category_required_credits | ✓ | 该类别要求学分（同方案同类别取首次出现的值） |
| course_code | ✓ | 课程编码 |
| course_name |  | 课程名（课程库不存在时用于自动创建） |
| credits |  | 课程学分（课程库不存在时用于自动创建） |
| is_required |  | 是否必修：`1/true/y/是/必修` 视为 true |
| semester_suggested |  | 建议学期，整数 |

## 四、成绩 `/imports/grades`

| 列 | 必填 | 说明 |
| --- | --- | --- |
| student_no | ✓ | 学号 |
| course_code | ✓ | 课程编码 |
| semester | ✓ | 学期标识，如 `2024-1` |
| credits_earned |  | 获得学分 |
| score |  | 分数 |
| status |  | 状态：`已完成 / 在修 / 挂科 / 重修` 或英文对应 |

> 同一学生 × 课程 × 学期已存在记录则**更新**，否则新建。

## 返回结构

```json
{
  "created": 12,
  "updated": 3,
  "skipped": 0,
  "errors": [
    {"row": 5, "message": "enroll_year 必须为整数"}
  ]
}
```

若 errors 不为空且没有任何写入，则整个事务回滚；否则提交已成功的行，错误行单独列出。
