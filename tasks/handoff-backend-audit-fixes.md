# 后端修改清单 · PR 审计整改（feat/backend）

> 来源：2026-06-28 PR 审计报告（main `043530a`），大脑已逐条回源码核实属实。
> 开工前先 `git merge main` 同步。定位：个人项目+简历+公开可复现，区分必修/加分，不过度工程。
> 分三批，按优先级做。每条都标了报告里的位置。

---

## 第一批 · 必修（解除阻断 + 安全，优先）

### B1. requirements.txt 补 sse-starlette + 锁大版本下限 🔴P0
- **问题**：`runs.py:11` import `sse_starlette`，但 `requirements.txt` 没列 → 第三方 pip 装完**后端起不来**（ModuleNotFoundError）。已核实属实。
- **修复**：requirements.txt 加 `sse-starlette`（PyPI 名带连字符）。顺便给关键依赖锁大版本下限（如 `fastapi>=0.115`、`openai>=1.85`、`neo4j>=6`），防大版本 breaking。

### B2. 加最简 API Key 鉴权中间件 🔴→建议必修
- **问题**：全后端零鉴权零 CORS（`main.py` 无任何 middleware，已核实）。公开仓库定位下，任何人 curl 可删库/耗 token/读全图谱。
- **修复**：加一个轻量中间件校验 `X-API-Key` header（密钥走 `.env` 新增字段如 `API_KEY`，**为空时跳过校验**以便本地无密钥也能开发）。`/health` 豁免。`DELETE /api/documents/{id}` 额外要求 `confirm=true` query 参数。
- **注意**：前端调用要带上这个 header（见前端清单 F0）——两边要协同，先定好 header 名和 .env 字段名：`API_KEY`。

### B3. LLM client 加 timeout + max_retries + 空响应防护 🟠P1
- **问题**：`llm.py:15` `OpenAI()` 无 timeout（httpx 默认 600s）、无 max_retries；`chat`/`chat_with_tools`/`embed` 取 `resp.choices[0]` 无空列表防护（部分兼容端点空 choices 会 IndexError）。已核实。
- **修复**：`OpenAI(..., timeout=httpx.Timeout(60, connect=10), max_retries=3)`；各调用处校验 `if not resp.choices: raise/降级`；`content` 返回 `or ""` 防 None。

### B4. 统一启动命令 + 去绝对路径（配合前端清单，但后端文档这边改） 🔴P1
- **问题**：`README.md:42` 用 `--factory create_app`，`运行说明.md:40`/`后端说明.md:62` 用 `app.main:app`——入口不一致；`运行说明.md:40,49` 写死 `D:\Anaconda3\envs\myself\python.exe`。已核实。
- **修复**：三份文档统一为 `app.main:app`（实际可跑的那个）；把 `D:\...\python.exe` 改为 `conda activate myself` 后用 `python -m uvicorn app.main:app --reload --port 8000`；README:35「启动命令将在实现后补充」改为实际步骤（已实现）。
- 注：`运行说明.md` 在仓库根，归后端窗口一并改（它最熟启动）。

---

## 第二批 · 强烈建议（运行时正确性）

### B5. BackgroundTasks 阻塞部分用 asyncio.to_thread 包裹 🟠P1
- **问题**：`tasks.py` 三个 `async def run_*` 内全是同步阻塞调用（parse/embed/execute_query/llm.chat），无 await → 入库时事件循环被独占，**SSE 冻结、像素动画实时性设计失效**（前端进度条卡住、最后一次性涌现）。注释自己已承认。已核实。
- **修复**：把阻塞段用 `await asyncio.to_thread(...)` 或 `starlette.concurrency.run_in_threadpool` 包裹。至少包 `ingest_document`、`extract_and_ingest`、`embed_chunks`、问答的 `answer_question_agentic`。注意 emit 事件的回调要线程安全（RunStore 操作）。

### B6. RunStore 终态 Run 加 TTL 清理 🟠
- **问题**：`store.py:17` `_runs` dict 永不移除，无 TTL/容量上限 → 长跑内存泄漏。
- **修复**：终态 Run 加 TTL（保留最近 N 分钟）或 LRU 淘汰；加 `_gc()` 约 10 行，在 create_run 时顺带清理过期。

### B7. 显式配 CORS（限定来源，禁 *） 🟠
- **修复**：`main.py` 加 `CORSMiddleware`，`allow_origins=["http://localhost:5173"]`，生产地址走 `.env`，**禁用 `"*"`**。

### B8. RunEvent timestamp_ms 加 alias 统一契约 + 删冗余 alias 🟠
- **问题**：`models.py:56` `timestamp_ms` 无 alias（输出下划线名），但 `Run` 用 camelCase（runId/createdAt），前端被迫处理两套命名；`models.py:55` `alias="answer"` 是 no-op 冗余。已核实。
- **修复**：`timestamp_ms` 加 `alias="timestampMs"`；删 `answer` 的冗余 alias。**前端要同步改 `types/runEvent.ts`**（见前端 F-契约）——两边协同，确认后再改。

### B9. embedding 维度运行时校验 🟠
- **问题**：`config.py` 硬编码 `embedding_dim=3072`，`embedding.py` 不验证实际维度 → 换模型忘改 EMBEDDING_DIM 时，错误延迟到写入/查询才暴露（L6 同类症状）。
- **修复**：`embed_chunks` 校验首向量长度 == 配置 dim，不符立刻抛明确错误。

### B10. 测试用独立索引名根治维度污染 🟠
- **问题**：L6 教训的残留风险——测试进程被强杀时 teardown 不执行，8 维 TEST_DIM 索引残留共享 Neo4j。当前 teardown 恢复只在正常退出有效。
- **修复（根治）**：测试用独立索引名（如 `chunk_embedding_test`）与生产物理隔离。需让 `search_chunks`/`ensure_schema` 支持索引名参数（测试传 test 名）。这是 lessons.md 记的根治方向。

### B11. 500 错误不泄露内部细节 🟠MEDIUM
- **问题**：`errors.py:36-39` 直返 `str(exc)`，暴露路径/库版本。
- **修复**：通用异常返回统一文案（如"服务内部错误"），详情仅 `logger.exception` 写日志。

---

## 第三批 · 加分（提升可观测/可解释，简历价值）

### B12. RunEvent 加 token_usage + 工具结构化字段 🟢
- 加 `tool_name`/`tool_input`/`tool_output`/`token_usage` 字段，让"可观测"从模糊变精确。注意：加字段要同步前端类型 + 不破坏现有 SSE 契约。

### B13. LLM 每轮 response 记 logger.debug 🟢
- agent 循环每轮把 LLM 完整 response 记 debug 日志，提升调试效率。

### B14. run_chat/run_ingest 加 asyncio.Semaphore(3) 限并发 🟢
- 防并发打爆 LLM rate limit。

### B15. PDF 页数/文本量上限 🟢
- `documents.py`/`pdf_parser.py` 加页数上限（如 200）或总文本量上限，防 PDF 炸弹。

### 暂不做（避免过度工程，报告也认同）
- Tool dataclass 抽象（待第 3 个工具）、Run 持久化落盘、熔断器、Redis/Celery。
- LLM prompt 注入分隔标记（报告标加分，个人项目优先级低，可选做 B 批之后）。

---

## 验证
- 每批做完跑 `pytest -q` 全过。
- B1 后：在干净环境 `pip install -r requirements.txt` 能起后端。
- B5 后：上传文档时 SSE 事件应**实时**流出（不是最后一次性涌现）。
- B8/B12 改契约的，与前端窗口对齐字段后再改，避免前后端不一致。
- DEVLOG 记录关键改动（尤其 B5 异步化、B10 根治思路）。

## 交接
分批 commit（每批可独立 commit），通知大脑分支名，大脑读 diff + 跑测试评审、合并。提交前先 `git merge main`。
