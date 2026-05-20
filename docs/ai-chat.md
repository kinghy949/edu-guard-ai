# AI 学业问答

## 设计

LLM 客户端只走 OpenAI 兼容的 `/chat/completions` 协议，可切换 OpenAI / DeepSeek / 通义 / Claude（任何兼容端点）。

```
.env:
  LLM_BASE_URL=https://api.deepseek.com/v1
  LLM_API_KEY=sk-...
  LLM_MODEL=deepseek-chat
```

## 上下文注入

每次对话由后端拼装 `system` 消息：

1. 固定 system prompt（角色定位 + 回答原则，见 `app/ai/prompts.py`）
2. 学生身份时附加「学生上下文」：培养方案、总学分要求、各分类已修/在修/缺口、推荐补修课、挂科记录（由 M2 比对引擎实时计算）
3. 教职工身份附加一段宏观提示

随后追加历史对话（最近 20 条）+ 本次用户输入。

**目的**：把"还差什么没修"的核心数据塞进 system，避免模型胡编课程名。

## 接口

| 路由 | 说明 |
| --- | --- |
| `GET /api/v1/chat/sessions` | 列出我的会话 |
| `POST /api/v1/chat/sessions` | 创建会话 |
| `GET /api/v1/chat/sessions/{id}/messages` | 历史消息 |
| `POST /api/v1/chat/sessions/{id}/messages` | 发送并同步获取回复 |
| `POST /api/v1/chat/sessions/{id}/messages/stream` | 发送并 SSE 流式接收 |
| `DELETE /api/v1/chat/sessions/{id}` | 删除会话 |

会话权限：仅创建者本人可读写。

## 流式响应（SSE）

前端订阅 `text/event-stream`，每个增量为：

```
data: <token 增量>

```

结束事件：

```
event: done
data: [DONE]
```

错误事件：

```
event: error
data: <错误描述>
```

流结束后，后端会把完整回复合并为一条 `assistant` 消息写入 `chat_messages`。
