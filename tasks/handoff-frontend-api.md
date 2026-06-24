# 前端交接清单 · 真实 API 接入收尾（feat/frontend）

> 大脑整理，交 feat/frontend 窗口执行。开工前：feat/frontend 已同步至最新 main（0bb1ae2，已确认）。
> GitHub 推送暂缓，只本地 commit。

## 一、要做什么（一句话）

把前端**仍在用 mock / 占位**的部分接到真实后端 API，让整个工作台端到端真跑通。

## 二、现状（已核实，重要——大部分已接通，别重复做）

**已接真实 API（不要动）：**
- 文档库 LibraryView：`GET/POST/DELETE /api/documents` ✓
- 问答区 WorkbenchView：`POST /api/chat` + SSE ✓
- 答案/引用区 CitationPanel：数据来自 SSE 终态 answer ✓
- 运行事件时间线 + AgentRoom：`useRunEvents` 接真实 SSE ✓

**本轮只需做这 3 件：**
1. **图谱可视化 GraphView**（仍 mock）→ 接真实 `/api/graph/*`
2. **设置页 SettingsView**（占位）→ 实现
3. **像素瑕疵微调**（上轮 AgentRoom 遗留：道具遮挡小人等）

## 三、任务 1：GraphView 接真实图谱 API

当前 `src/views/GraphView/GraphView.tsx` 用 `mockGraph` 硬编码。改为调后端（API 已就绪）：

| 用途 | 后端 API | 响应结构 |
|---|---|---|
| 加载全图 | `GET /api/graph/entities?limit=100` | `{nodes:[{id,name,type,documentId}], edges:[{source,target,type,confidence}]}` |
| 实体邻域展开 | `GET /api/graph/entities/{entity_id}/neighbors` | 同上 `{nodes,edges}`（中心+1跳） |
| 实体搜索 | `GET /api/graph/search?q=xxx&limit=20` | `[{id,name,type,documentId}]`（只返点不返边） |

- 用 `apiFetch`（`src/api/client.ts`）调用。
- **注意字段对齐**：后端返回 `{nodes:{id,name,type,documentId}, edges:{source,target,type,confidence}}`，前端 `src/types/graph.ts` 的 `GraphNode{id,label,entityType}`/`GraphEdge{id,source,target,relationType}` 字段名**不一致**（label↔name、entityType↔type、relationType↔type）。需要一层映射（后端 name→前端 label、type→entityType/relationType）。在 GraphView 或 api 层做映射，别改后端。
- Cytoscape 渲染逻辑、搜索、实体详情面板这些 UI 已有，只换数据源。
- 删掉对 `mockGraph` 的 import（`src/mocks/` 届时无生产引用，可保留供测试）。
- 空图处理：图库可能没数据（没上传过文档），要有空态提示，别白屏。

## 四、任务 2：SettingsView 实现

当前 `src/views/SettingsView/SettingsView.tsx` 是占位。实现（参考其占位注释里写的方向）：
- **依赖连通状态**：调 `GET /health/deps`，展示 Neo4j（ok/error）、LLM（configured/not_configured）状态。
- 模型配置提示：只读展示（模型配置在后端 .env，前端不改 .env，只提示用户去配）。
- 样本导入说明（可选）。
- 保持浅色专业基调，复用现有 UI 基件（Button/Card/Panel/StatusBadge 等）。

## 五、任务 3：AgentRoom 像素瑕疵微调

上轮遗留（todo 标 `[~] 动画不遮挡主工作流`）：
- **道具遮挡小人**：deleting 碎纸机等道具盖住了小人主体，调整道具位置放小人旁/前，不遮挡。
- 其他你觉得不协调的细节（小人比例、房间留白等）可一并微调。
- 仍守红线：stage 只来自真实 RunEvent，devControls 仅开发预览。

## 六、边界与约定

- **不改后端、不改契约**：前后端字段不一致时在前端做映射层。
- **真实后端要在跑**：联调需后端 `uvicorn` 起着 + Neo4j 起着。Neo4j 跨 worktree 共享，后端窗口此时在做评估也会用 Neo4j，**错峰**。
- **装依赖先问**（一般不用新依赖，Cytoscape 已装）。
- **DEVLOG**：完成后 `frontend/DEVLOG.md` 追加记录。
- 验证：`npm run typecheck` + `npm run build` 通过；手动起后端联调确认图谱/设置页真出数据。

## 七、验收

- [ ] GraphView 显示真实图谱（上传文档后能看到真实实体/关系），搜索/邻域展开走真实 API
- [ ] SettingsView 显示真实依赖连通状态
- [ ] AgentRoom 道具不再遮挡小人
- [ ] typecheck/build 通过

## 八、交接

本地 commit（写清做了什么），口头通知大脑分支名，大脑读 diff 评审、合并。不自行合并 main，不 push。
