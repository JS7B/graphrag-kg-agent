# 大脑裁决：文档/图谱 API + Run/事件流 — 拆 A/B 交付

> 后端窗口（feat/backend）原计划把「文档上传 API」+「Run 与事件流」合并成一个大板块。
> 大脑 review 后裁决：**拆成 A、B 两个独立交付，先 A 后 B**。本文件是最终计划，照此执行。
> 开工前先 `git merge main` 同步。

## 为什么拆（裁决理由，便于理解）

后端计划本身思路清晰（五处取舍——不用第三方框架、内存 RunStore、BackgroundTasks、SSE 终态带 answer、camelCase alias——大脑全部认同）。但合并成一个大板块有三个风险：

1. **交付周期过长** — 前端 mock→真实切换要等阶段 2/3 全做完，中间无独立里程碑。
2. **大板块 review 难一次看清** — 之前 PDF 偏移 bug 正是被测试掩盖的缺陷，板块越大越难抓。
3. **/api/chat 异步化是范围蔓延** — 会破坏已验证契约 + 影响前端，不应和上传捆在一起。

拆成 A/B 后：A 小、独立、可立刻验证（前端 mock→真实上传）；B 大、涉及异步，独立 review 风险可控。

---

## A 板块：文档上传/入库 API（本轮做）

**范围（做什么）：**
- `POST /api/documents` — multipart 上传单文件（`.md`/`.txt`/`.pdf`），**同步**跑完整入库链路，返回结果摘要。
- `GET /api/documents` — 文档列表（**从 Neo4j 查 Document 节点**，含状态字段）。
- `GET /api/documents/{id}` — 单文档详情。
- **Document 状态字段**：`parse_status` / `index_status` / `chunk_count` / `name` / `source_type`，落到 Neo4j Document 节点。写入时由 `ingest_document` 顺手 SET（无需额外步骤）。

**入库链路（复用已有函数，A 板块核心）：**
```
1. 接收文件 → 校验扩展名（md/txt/pdf）→ 写临时文件
2. parse_file(path)                          # app.parsing.base
3. embed_chunks(doc.chunks)                  # app.graph.embedding
4. ingest_document(driver, doc, embeddings)  # app.graph.writer（写入时 SET 状态字段）
5. extract_and_ingest(driver, doc)           # app.extraction.pipeline
6. 删除临时文件（try/finally）
```

**A 板块关键约束（避免踩坑）：**
- **同步执行** — 不引入 Run/Event/BackgroundTasks/SSE，这些都是 B 的事。A 就是同步跑完返回。
- **document_id 沿用 parse_file 内部生成的稳定 id**，别在路由里另造（否则破坏 chunk_id 幂等）。
- **幂等是硬测试要求** — 重复上传同一文件，chunk/entity 不翻倍（对应「图谱无重复」硬规则）。
- **driver 取 `request.app.state.neo4j`**，和 `/api/chat` 一致。
- **扫描版 PDF 沿用 parse_pdf 的 warning 降级**，不额外处理。

**新增配置：**
- `MAX_UPLOAD_MB: int = 10` 加进 `Settings`（走环境变量，`.env.example` 同步）。

**响应格式（成功 200，camelCase alias 沿用 chat 路由模式）：**
```json
{
  "documentId": "...",
  "documentName": "原始文件名",
  "chunkCount": 12,
  "extraction": {
    "entityCount": 8, "relationCount": 6, "mentionCount": 14, "failedChunks": 0
  }
}
```
错误响应沿用项目统一结构 `{error:{type,message}}`：400 不支持类型 / 413 超大 / 500 入库失败。

**测试要求（TDD，真连 Neo4j，沿用 test_ 前缀自清理夹具）：**
1. 上传 .md/.txt/.pdf → 200，chunkCount/entityCount 正数，documentId 稳定
2. **重复上传同一文件 → chunk/entity 不翻倍**（幂等硬要求）
3. 不支持扩展名（.docx）→ 400
4. 超大文件（超 MAX_UPLOAD_MB）→ 413
5. 上传后 `/api/chunks/{chunk_id}` 能反查（端到端贯通）
6. 临时文件请求结束后不存在
7. GET /api/documents 返回的列表含状态字段

**文件组织：** `backend/app/routers/documents.py` + `backend/tests/routers/test_documents.py`，main.py include_router。

**依赖：** 不新增。FastAPI 内置 multipart；若运行时报缺 `python-multipart`，先 `pip show` 确认，**装前必须先问用户**。

---

## B 板块：Run 与事件流（A 合并后再做，本轮不碰）

**A 合并后才开工。** 范围：

- `backend/app/runs/`：`models.py`（Run/RunEvent + Stage 枚举，**12 个 Stage 是前端契约不可改**）、`store.py`（内存注册表 + asyncio.Queue SSE 订阅）、`tasks.py`（run_ingest 后台任务，按 6 阶段 emit 事件）
- `routers/runs.py`：`GET /api/runs/{id}/events/stream`（SSE）、`/events`（历史）、`GET /api/runs/{id}`
- `routers/graph.py`：`/entities`、`/entities/{id}/neighbors`、`/search?q=`
- **改 routers/documents.py**：POST 改为起后台 Run（异步化），返回 `{runId, document}`
- **改 routers/chat.py**：POST /api/chat 异步起 Run，SSE 终态事件带 answer（**这一条是用户明确要求**，前端冲突到时解决）

**Stage 枚举（前端契约，12 个，不可改）：**
入库：uploading→parsing→extracting→linking→indexing→done
问答：searching→checking→writing→done
删除：deleting→done

**B 板块的关键取舍（沿用后端原计划的合理部分）：**
- 内存 RunStore（非 Neo4j 持久化）— Run 是瞬态进度，重启丢失可接受
- BackgroundTasks（非 Celery）— 单进程够演示
- SSE 终态带 answer — 少一次往返
- Document 状态字段：写入时落 Neo4j（A 已做），B 阶段 GET 直接查图库
- chat 异步化：**用户已确认要做**，前端契约冲突届时处理

---

## DELETE 语义（B 板块做，但开工前必须在计划里写明）

DELETE 牵涉级联 + 多文档共享问题，开工前先回答：

- **级联范围**：删 Document 时，删其全部 Chunk + HAS_CHUNK 边。MENTIONS 边随 Chunk 删除。
- **Entity 多文档共享处理**（关键）：删文档 A 时，**不删共享 Entity**（被其他文档 MENTION 的 Entity 保留）。只删：
  - 该文档独占的 Entity（仅被本文档 MENTION 的）
  - 该文档的 RELATES 关系（两端实体都不留时才删关系）
- DELETE 起一个 `deleting` Run，emit deleting→done 事件。

> 这条是 B 板块开工前的「不确定点」，开工前问大脑确认，别自行决定级联策略。

---

## 交接流程

1. **A 板块开工前**：`git merge main` 同步（拿本裁决文件）。
2. A 实现完：本地 commit（`feat(documents): 文档上传入库 API + Document 状态字段`）→ `git merge main` → 通知大脑 `feat/backend` 评审。
3. 大脑 review A 通过 → 合并 main → 更新 todo。
4. **B 板块开工**：`git merge main`，DELETE 语义先和大脑确认，再实现。
5. B 完成同样流程。

## 不在本轮做（明确划出）

- 前端代码改动（归 feat/frontend）
- 跨进程队列（Celery/RQ）
- S3/对象存储抽象
- 分片上传、断点续传
- 问答的 Run 化（归 B，A 不碰 chat）
