# 前端契约层改造规格（对齐 B 板块新契约）

> 大脑窗口产出。前端窗口（feat/frontend）照此改造，完成后 commit + 通知大脑评审。
> **本轮只做契约层改造，不做像素小人动画**（下一轮再做）。
> 开工前先 `git merge main` 同步（feat/frontend 落后 main 6 个提交，要拿 B 板块的类型 + 新接口）。

## 背景：契约变了

B 板块把后端从"同步请求/响应"改成了"起异步 Run + SSE 进度流"。前端现在所有 mock 调用都按旧同步契约，**必须先改造契约层，后续才能接真实数据 + 像素小人**。

旧 → 新的核心区别：
```
旧：apiFetch(POST /api/documents) → 直接拿 {chunkCount, extraction} 渲染
新：apiFetch(POST /api/documents) → 拿 {runId, documentId}
    → 订阅 SSE /api/runs/{runId}/events/stream
    → 边收事件边更新 UI（进度/状态徽标）
    → 终态事件后刷新文档列表
```

## 范围（做什么 / 不做什么）

**做：**
1. 新建 **SSE 客户端**（封装 `EventSource`，含历史兜底、终态自动关闭、错误处理）。
2. 改造 **`useRunEvents` Hook**：接 `runId` 参数，订阅真实 SSE，累积事件，派生 `currentStage`。
3. 统一 **`RunEvent` / `RunEventStatus` 类型**对齐后端（后端已合并，改前端）。
4. 4 个业务场景改成 **"起 Run → 订阅 → 驱动 UI"** 模式：
   - 文档上传（POST /api/documents）
   - 文档删除（DELETE /api/documents/{id}）
   - 问答（POST /api/chat）
   - 文档列表/详情/图谱查询（这些是普通 GET，**不用 SSE**，保持 apiFetch）
5. UI 反映 stage 进度（RunEventTimeline 接真实事件、文档状态徽标随事件变化）。**不画像素小人动作**，本轮 PixelAgent 保持 idle 占位。

**不做（明确划出）：**
- ❌ 像素小人 12 状态动画（下一轮，你亲调）
- ❌ 问答区答案流式渲染（本轮 chat 订阅 SSE 只更新 stage 进度，终态 answer 拿到后整体显示即可，不做打字机效果）
- ❌ 重新设计视图布局、视觉打磨（本轮纯契约层，不动布局）

## 契约对齐细节（必须改的点）

### 1. `RunEventStatus` 枚举统一（前端改）

前端现状：`'started' | 'progress' | 'done' | 'failed'`
后端实际：`'running' | 'succeeded' | 'failed'`

**改前端 `types/runEvent.ts`** 对齐后端：
```ts
export type RunEventStatus = 'running' | 'succeeded' | 'failed'
```

### 2. `RunEvent` 类型补字段

后端 SSE 事件 payload（camelCase）：
```ts
export interface RunEvent {
  stage: Stage
  status: RunEventStatus
  message: string
  answer: Answer | null   // ← 新增。仅问答终态(succeeded)事件携带
  timestampMs: number     // ← 改名 timestamp → timestampMs（对齐后端 by_alias 输出）
}
```

> 确认点：后端 `RunEvent.timestamp_ms` 用 `Field(default_factory=...)` 但**没加 alias**，`by_alias=True` 输出仍是 `timestamp_ms`（下划线）。**开工前让前端在 SSE 客户端里把 `timestamp_ms` 映射成 `timestampMs`，或在类型里用 `timestamp_ms`**——这一点开工时实测一个事件确认，别假设。大脑倾向：前端类型就用 `timestamp_ms`（和后端一致，少一层转换）。

### 3. `Answer` / `Citation` 类型确认

后端 chat 终态事件的 `answer` 结构（camelCase）：
```json
{
  "question": "...",
  "text": "...",
  "citations": [
    {"index": 1, "chunkId": "...", "documentName": "...", "location": "...", "snippet": "..."}
  ]
}
```
对照前端现有 `types/answer.ts`，确认字段对齐。**如不对齐，改前端对齐后端**（后端已验证）。

## 新建：SSE 客户端模块

新文件 `frontend/src/api/sse.ts`，导出一个 `subscribeRunEvents` 函数：

```ts
// 伪代码示意，不是最终实现
export function subscribeRunEvents(
  runId: string,
  onEvent: (event: RunEvent) => void,
  onError: (err: Event) => void,
): () => void  // 返回取消订阅函数
{
  // 1. new EventSource(`${BASE_URL}/api/runs/${runId}/events/stream`)
  // 2. onmessage: JSON.parse → 校验 → onEvent
  // 3. 收到 status=succeeded|failed → 自动 close（终态）
  // 4. onerror → onError + close
  // 5. 返回 cleanup 函数（close EventSource）
}
```

**关键设计点：**
- 终态(succeeded/failed)事件收到后**立即关闭** EventSource，不留连接。
- BASE_URL 复用 `api/client.ts` 的 `VITE_API_BASE_URL`（抽出来共享，别复制）。
- 历史兜底：本轮先不做断线重连 + `/events` 补全（简单优先），EventSource 自带重连够用。如需补全再迭代。

## 改造：`useRunEvents` Hook

```ts
// 伪代码示意
export function useRunEvents(runId: string | null) {
  const [events, setEvents] = useState<RunEvent[]>([])
  const [currentStage, setCurrentStage] = useState<Stage>('idle')

  useEffect(() => {
    if (!runId) return
    const unsubscribe = subscribeRunEvents(
      runId,
      (event) => {
        setEvents(prev => [...prev, event])
        setCurrentStage(event.stage)
      },
      (err) => { /* 错误处理：可设 error state */ }
    )
    return unsubscribe
  }, [runId])

  return { events, currentStage }
}
```

**红线保留**：`currentStage` 只从真实事件派生，禁止前端编造（硬规则，已有注释）。

## 4 个业务场景改造

### 场景 1：文档上传（LibraryView 的上传入口）
```
旧：POST /api/documents → 直接渲染 chunkCount
新：POST /api/documents → 拿 {runId, documentId}
    → useRunEvents(runId) 订阅
    → 进度：stage uploading→parsing→extracting→indexing 在 RunEventTimeline 显示
    → 终态 succeeded → 刷新 GET /api/documents 列表
    → 终态 failed → 显示错误 message
```

### 场景 2：文档删除
```
DELETE /api/documents/{id} → 拿 {runId}
→ 订阅，stage deleting→done
→ 终态 succeeded → 刷新列表
```

### 场景 3：问答（WorkbenchView）
```
POST /api/chat → 拿 {runId}
→ 订阅，stage searching→checking→writing 在时间线显示
→ 终态 succeeded 事件带 answer → 渲染答案 + citations
→ 终态 failed → 显示错误
```

### 场景 4：GET 类接口（不变）
```
GET /api/documents、/api/documents/{id}、/api/graph/entities、
/api/graph/entities/{id}/neighbors、/api/graph/search?q=、/api/chunks/{id}
→ 保持 apiFetch，不走 SSE
```

## mock 处理

现有 `mocks/index.ts` 的 mock 数据**本轮保留**（GET 类接口 mock 还有用，比如离线开发）。但**上传/删除/问答的 mock 响应要按新契约改**：返回 `{runId, documentId}` 而非完整结果，且 mock 一条 SSE 事件流（可以用 setTimeout 模拟 stage 推进）。

> 如果 mock SSE 太复杂，可以**暂时让上传/删除/问答直连真实后端**（开发环境后端在 localhost:8000），GET 类保留 mock。这个开工时权衡，大脑倾向后者（简单）。

## 验收标准

1. **typecheck 通过**（`npm run typecheck` 零错误）。
2. **build 通过**（`npm run build`）。
3. **契约对齐验证**：起后端（`uvicorn app.main:app`），前端上传一个小 .md 文件，能看到：
   - 上传后立即返回 runId（不再等完整结果）
   - RunEventTimeline 显示真实 stage 推进（uploading→parsing→...→done）
   - 终态后文档列表刷新，新文档出现
4. **问答契约验证**：问一个问题，看到 stage 推进 + 终态答案带引用显示。
5. **删除契约验证**：删除一个文档，stage 推进 + 列表刷新。
6. **像素小人保持 idle**（本轮不动画，验证它没被误触发其他状态）。
7. **GET 类接口不受影响**（文档列表、图谱查询正常）。

## DEVLOG 要求

在 `frontend/DEVLOG.md` 追加一条，按 AGENTS.md 模板。建议覆盖：
- SSE / EventSource 怎么工作（浏览器原生 SSE 机制）
- 为什么后端从同步改异步（长任务阻塞 + 进度可见性）
- 终态自动关闭 EventSource 的重要性（不留僵尸连接）
- useRunEvents 的红线（currentStage 只从真实事件派生）

## 交接流程

1. 开工前 `git merge main`（拿 B 板块契约 + 本规格文件）。
2. 实现完：本地 commit（`feat(frontend): 契约层改造对齐 B 板块异步 + SSE`）→ `git merge main` → 通知大脑 `feat/frontend` 评审。
3. 大脑 review 通过 → 合并 main → 更新 todo。
4. 下一轮：像素小人 12 状态动画（你亲调）。

## 不确定的点（开工前问大脑）

- `timestamp_ms` vs `timestampMs`：开工时实测一个 SSE 事件确认字段名，再定类型。倾向 `timestamp_ms`（和后端一致）。
- mock SSE 是否值得做：大脑倾向不做，开发环境直连真实后端更简单。
- 问答答案流式渲染：本轮不做，终态整体显示。如你认为必要可以本轮做，但工作量增加。
