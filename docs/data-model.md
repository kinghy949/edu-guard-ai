# 核心数据模型

> 仅为初版设计，会随 M1 实现迭代。

## 实体

### User（用户）
- id, username, password_hash, role(student/counselor/admin), email, phone, status

### Student（学生扩展）
- id, user_id, student_no, name, gender, enroll_year, college, major, class_name, program_id

### Program（培养方案）
- id, code, name, college, major, version, total_credits_required

### CreditBucket（学分桶 / 分类要求）
- id, program_id, category(必修/限选/任选/通识/实践/创新创业/...), credits_required, note

### Course（课程）
- id, code, name, credits, category_default, hours, semester_suggested

### ProgramCourse（培养方案-课程映射）
- id, program_id, course_id, bucket_id, is_required

### Grade（成绩 / 选课记录）
- id, student_id, course_id, semester, credits_earned, score, status(完成/在修/挂科/重修)

### Warning（预警）
- id, student_id, level(提示/警告/严重), semester, summary, detail(JSON), created_at, resolved_at

### Notification（通知记录）
- id, warning_id, channel(站内/email/wecom/dingtalk/sms), target, status, sent_at, payload

### NotificationConfig（通知渠道配置）
- id, channel, enabled, config(JSON), updated_by, updated_at

### ChatSession / ChatMessage（AI 问答）
- id, student_id, role(user/assistant), content, created_at

## 关系草图

```
User 1──1 Student n──1 Program 1──n CreditBucket
                                  │
                                  └──n ProgramCourse n──1 Course
Student 1──n Grade n──1 Course
Student 1──n Warning 1──n Notification
```
