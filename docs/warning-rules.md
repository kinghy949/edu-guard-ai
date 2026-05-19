# 预警规则

## 输入

- 学生 + 培养方案 + 学生所有成绩
- 学分桶分类（必修 / 限选 / 任选 / 通识 / 实践 / 创新创业 …）
- 学生入学年份（用于估算当前所处学期阶段）

## 完成度计算

成绩状态映射：

| 状态 | 学分归类 |
| --- | --- |
| `completed` | earned（已修） |
| `in_progress` / `retake` | in_progress（在修） |
| `failed` | 不计入任何桶，单独列入 `failed_courses` |

每个桶：`gap = max(required - earned - in_progress, 0)`

方案外课程归入虚拟桶 `__other__`，不抵消方案缺口。

## 阶段估算

```
stage = max((当前年 - 入学年) * 2 + (上半年=1 / 下半年=2), 1)
expected_completion_ratio = min(stage / 8, 1.0)
```

按 4 年制 8 学期计。可在 `WarningRule.stage_total_semesters` 调整。

## 分级规则（默认）

| 级别 | 触发条件（满足其一） |
| --- | --- |
| `severe` 严重 | 存在挂科未通过 / 必修类完成度 < 50% / `expected > 0.5` 且总缺口比 > 50% |
| `warn` 警告 | 总缺口比 > 25% / 任一桶完成度 < 70% |
| `info` 提示 | 总缺口 > 0 |

> 阈值由 `app.services.warning_engine.WarningRule` 集中维护，部署方可覆盖。

## 触发方式

- 手动：`POST /api/v1/warnings/generate`（支持按 college/major/enroll_year/student_ids 过滤）
- 单人：`POST /api/v1/warnings/students/{student_id}/generate`
- 自动（M3 接入定时任务后）

## 输出（写入 `warnings.detail` JSON 字段）

```json
{
  "stage": 6,
  "expected_completion_ratio": 0.75,
  "actual_completion_ratio": 0.58,
  "total_gap": "32.5",
  "total_required": "160",
  "buckets": [
    {"category": "必修", "required": "80", "earned": "44", "in_progress": "4", "gap": "32"},
    {"category": "限选", "required": "30", "earned": "20", "in_progress": "0", "gap": "10"}
  ],
  "failed_count": 1
}
```
