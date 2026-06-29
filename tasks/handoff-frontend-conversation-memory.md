# 前端交接清单 · 多轮对话记忆（feat/frontend）

> 大脑整理，交 feat/frontend 窗口执行。**开工前先 `git merge main` 同步最新 main。**
> 与后端并行：前后端通过下方「冻结契约」解耦。**联调前先读这份契约**，后端按此输出，前端按此对接。
> 真实后端要在跑才能联调（uvicorn :8000 + Neo4j 起着）。Neo4j 跨 worktree 共享，**错峰**用。

## 一、要做什么（一句话）

把工作台从「每次提问孤立单轮」升级为**多会话多轮对话**：左侧会话列表（新建/切换/删除），中间对话区连续追问，Agent 能记住本会话上下文；刷新页面会话列表和历史都在。

## 二、冻结契约（与后端共用，前端严格按此对接）

### 2.1 POST /api/chat（改：请求/响应加 conversationId）

**请求体**：
```json
{ "question": "...", "conversationId": null }
```
- `conversationId`: 首问传 `null`/不传；追问传上一问返回的值。

**响应体**：
```json
{ "runId": "abcd1234ef56", "conversationId": "conv_xxxxxxxxxxxx" }
```
- `conversationId`：**始终返回**。首问时拿到新会话 id，**前端必须存住**，后续追问回传。

**SSE 终态事件**：`answer` 字段结构**不变**（`{text, confidence, citations}`），现有订阅逻辑不动。

### 2.2 会话 CRUD（新接口）

```
GET    /api/conversations                  → 会话列表
POST   /api/conversations                  → 新建空会话（请求体可选 {title?}）
GET    /api/conversations/{conversationId} → 单会话 + 全部消息
DELETE /api/conversations/{conversationId} → 删会话（同步）
```

**GET /api/conversations 响应**（createdAt 降序）：
```json
{ "items": [ { "conversationId": "...", "title": "...", "createdAt": 1719000000000, "messageCount": 6 } ] }
```

**GET /api/conversations/{id} 响应**：
```json
{
  "conversationId": "...", "title": "...", "createdAt": 1719000000000, "messageCount": 6,
  "messages": [
    { "messageId": "conv_aaaa#1", "turnIndex": 1, "role": "user",  "text": "...", "confidence": null, "citations": [] },
    { "messageId": "conv_aaaa#2", "turnIndex": 2, "role": "agent", "text": "...", "confidence": "high", "citations": [{...}] }
  ]
}
```
- `role`: `"user"` | `"agent"`
- `confidence`: `"high"|"medium"|"low"`（user 为 `null`）
- `citations`: 与 chat answer.citations 同结构（`{index, chunkId, documentId, location, snippet}`）；user 消息为 `[]`

**DELETE**：成功返回 204 或 `{deleted:true}`（前端按 res.ok 判断即可）。

## 三、现状（已核实，别重复做）

- `WorkbenchView.tsx`：现有 `messages` state 已累积渲染（视觉层 OK），但后端不感知历史、刷新即丢。`ChatRequest` 只发 `{question}`。
- `useRunEvents`、`ChatThread`、`CitationPanel`、SSE 订阅逻辑：**不动**，照旧。
- `api/client.ts::apiFetch`：复用，会话 API 走它。

## 四、实现要点

### 1. 类型（新增 `src/types/conversation.ts`）

```ts
export interface Conversation {
  conversationId: string
  title: string
  createdAt: number
  messageCount: number
}
export interface ConversationMessage {  // 对话消息（图谱 Message 的前端形态）
  messageId: string
  turnIndex: number
  role: 'user' | 'agent'
  text: string
  confidence: 'high' | 'medium' | 'low' | null
  citations: Citation[]   // 复用 types/answer.ts 的 Citation
}
export interface ConversationDetail extends Conversation {
  messages: ConversationMessage[]
}
```
- `src/types/index.ts`：re-export。

### 2. API 封装（新增 `src/api/conversations.ts`）

```ts
listConversations(): Promise<{ items: Conversation[] }>
createConversation(title?: string): Promise<ConversationDetail>
getConversation(id: string): Promise<ConversationDetail>
deleteConversation(id: string): Promise<void>
```
全走 `apiFetch`。DELETE 用 `res.ok` 判断（apiFetch 对 204 可能无 body，注意处理——参考现有用法，必要时直接 fetch 或 apiFetch 容错）。

### 3. 会话状态管理（改 `WorkbenchView.tsx`，核心）

新增 state：
- `conversationId: string | null` —— 当前会话 id
- `conversations: Conversation[]` —— 会话列表（侧边栏）

流程改造：
- **首次进入**：`listConversations()` 加载侧边栏；默认不自动选任何会话（空态引导「新建会话开始」），或可选最近一条——**建议空态引导，避免一进来就拉历史**。
- **新建会话**：点「新建」→ `createConversation()` → 拿到 id → 设为当前会话 → 清空 messages → 侧边栏 unshift 新条目。
- **提问 `handleSend`**：
  - 必须有当前 conversationId（无则先建会话，或提示新建）。
  - POST `/api/chat` body 带 `conversationId`；响应的 conversationId 存住（首问时可能与请求不同——后端首问新建）。
  - 终态落 agent 消息后，**只清 chatRunId 解除 busy，不清 conversationId**（关键改动，现有代码终态会清 runId——保留这个，但别顺手清会话）。
  - 终态后侧边栏对应会话的 `messageCount` +2、title 若是默认「新会话」则更新为首问前若干字（或简单重新拉一次列表）。
- **切换会话**：`getConversation(id)` → 把 `messages` 回灌（把 ConversationMessage 转成现有 ChatMessage：role/text/answer），设 conversationId，清 chatRunId。
- **删除会话**：`deleteConversation(id)` → 从列表移除；删的是当前会话则清空、回到空态。
- **刷新恢复**：页面挂载时若有「上次会话」可记 localStorage（conversationId），恢复时 `getConversation` 拉历史。可选增强，不强求。

### 4. 会话侧边栏（新增组件 `src/components/ConversationSidebar/`）

- 会话列表（title + 时间 + 消息数）+ 高亮当前会话。
- 顶部「新建会话」按钮。
- 每条可删除（小按钮/右键，带二次确认防误删）。
- 复用现有 UI 基件（Button/Card/Panel 等）+ tokens.css，风格对齐 Linear/Notion 工程感。
- 空列表态提示。

### 5. 布局调整（`WorkbenchView.tsx`）

现有是「左右两列」（对话区 | AgentRoom+Timeline）。改为**三列**：
```
[ 会话侧边栏 ] [ 对话区(ChatThread+CitationPanel+ChatComposer) ] [ AgentRoom + Timeline ]
```
- 侧边栏可固定窄宽（如 240px），响应式：窄屏可折叠。
- 保持重点信息清晰、不拥挤（硬指标）。

### 6. 历史消息渲染回看

`getConversation` 返回的 ConversationMessage 转成 ChatMessage 时：
- user 消息 → `{role:'user', text}`
- agent 消息 → `{role:'agent', text, answer:{text, confidence, citations}}`（让 CitationPanel/角标点击逻辑复用，无需改 CitationPanel）。
- turnIndex 用于排序（后端已按 turnIndex 升序返回，直接用）。

## 五、硬规则与边界

- **不改后端、不改契约**：字段名以后端输出为准（camelCase），前端类型与之对齐。
- **红线守**：AgentRoom 的 stage 仍只来自真实 RunEvent，不伪造（本次不碰 AgentRoom 动画）。
- **无障碍不退化**：侧边栏会话项、新建/删除按钮需键盘可达、`:focus-visible`、aria-label；删除二次确认对话框也需键盘可达（参考现有 PR 审计 F1-F15 的标准）。
- **prefers-reduced-motion**：新加的过渡动画要尊重。
- **typecheck + build**：改了导出/类型后**务必跑 build**（`tsc -b` 比 `tsc --noEmit` 严，见前端说明.md §2）。
- **DEVLOG**（`frontend/DEVLOG.md`）：多会话状态管理思路、布局调整踩坑（若有）。

## 六、验收

- [ ] 侧边栏列出会话、新建/切换/删除可用
- [ ] 同会话连续追问，第二轮能体现「记得上文」（联调后端就绪后）
- [ ] 切换会话，历史对话完整恢复（含引用角标可点）
- [ ] 刷新页面，会话列表仍在（至少 listConversations 能拉回）
- [ ] 会话隔离：A 会话历史不串到 B 会话
- [ ] 布局三列不拥挤，侧边栏键盘可达
- [ ] `npm run typecheck` 零错误、`npm run build` 通过（Cytoscape 650KB 警告忽略）

## 七、联调依赖

后端会话 API 就绪前，前端可先用**本地 mock**打通 UI 与状态管理流（mock 一份 listConversations/getConversation 返回），但**最终必须接真实后端验证**（动画/引用红线都依赖真实数据）。后端就绪后切真实，删 mock。

## 八、交接

本地 commit（写清做了什么），**口头通知大脑分支名**，大脑读 diff 评审、合并。**不自行合并 main，不 push。**
