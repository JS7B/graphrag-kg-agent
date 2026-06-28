"""后台任务：把入库/问答/删除的同步链路包成「带进度事件」的异步执行单元。

BackgroundTasks 在事件循环线程跑，但入库/问答的同步阻塞调用（parse/embed/llm/
execute_query）会独占事件循环——导致 SSE 推送冻结、前端进度条卡住、像素动画实时性
失效。故把阻塞段用 asyncio.to_thread 丢到线程池，让事件循环空闲时能即时推送 SSE。

跨线程 emit 处理（关键）：run_chat 把 answer_question_agentic 整个包进 to_thread，
agent 在工作线程内通过 on_event 回调 emit 事件。RunStore（dict/asyncio.Queue）非
线程安全，工作线程不能直接调 store.append_event。用 loop.call_soon_threadsafe 把
emit 操作投递回事件循环线程执行，保证 RunStore 只在单线程访问。

每个任务全程 try/except：BackgroundTasks 会吞掉异常，失败必须自己 emit error +
run.status=failed，否则前端 SSE 流永不关闭、像素 Agent 卡在中间状态。
"""

import asyncio
import logging
import os
import tempfile

from neo4j import Driver

from app.clients import llm
from app.extraction import extract_and_ingest
from app.graph import embed_chunks, ingest_document
from app.parsing import parse_file
from app.qa.agent import ToolCallingUnsupported, answer_question_agentic
from app.qa.pipeline import answer_question
from app.runs.models import RunEvent, RunStatus, Stage
from app.runs.store import RunStore

logger = logging.getLogger(__name__)

# LLM 并发上限（B14）：个人单用户场景，3 足够防并发打爆 rate limit。
# Python 3.10+ 的 asyncio.Semaphore 不再绑定具体 loop，模块级创建安全。
_LLM_SEMAPHORE = asyncio.Semaphore(3)


def _emit(store: RunStore, run_id: str, stage: Stage, status=RunStatus.RUNNING, **kw):
    """记一条进度事件。失败时 status=FAILED，成功终态 status=SUCCEEDED。"""
    store.append_event(run_id, RunEvent(stage=stage, status=status, **kw))


async def run_ingest(
    driver: Driver,
    store: RunStore,
    run_id: str,
    file_bytes: bytes,
    filename: str,
    doc_type: str,
) -> None:
    """入库后台任务：uploading→parsing→extracting→indexing→done。

    document_id 用源文件名，保证 chunk_id 幂等（与 A 板块同步路由一致）。
    """
    try:
        _emit(store, run_id, Stage.UPLOADING, message=f"接收 {filename}")
        source_name = os.path.basename(filename)

        _emit(store, run_id, Stage.PARSING, message="解析文档")
        # parse_file 需要文件句柄（PDF/Markdown），落临时盘再解析；finally 清理。
        suffix = os.path.splitext(source_name)[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix, prefix="run_") as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name
        try:
            doc = await asyncio.to_thread(parse_file, tmp_path, document_id=source_name)
        finally:
            try:
                os.remove(tmp_path)
            except OSError:
                pass

        _emit(store, run_id, Stage.EXTRACTING, message="生成向量并写入图库")
        # embed/ingest 是同步阻塞（HTTP/Cypher），包 to_thread 不冻结事件循环
        embeddings = await asyncio.to_thread(embed_chunks, doc)
        await asyncio.to_thread(
            ingest_document, driver, doc, embeddings, name=source_name, source_type=doc_type
        )

        _emit(store, run_id, Stage.INDEXING, message="抽取实体与关系")
        stats = await asyncio.to_thread(extract_and_ingest, driver, doc)

        _emit(
            store, run_id, Stage.IDLE, RunStatus.SUCCEEDED,
            message=(
                f"入库完成：{stats.entity_count} 实体 / "
                f"{stats.relation_count} 关系 / {len(stats.failed_chunks)} 失败 chunk"
            ),
        )
    except Exception as exc:  # noqa: BLE001 — 后台任务必须吞异常并记录
        logger.exception("入库任务失败 run=%s", run_id)
        _emit(store, run_id, Stage.ERROR, RunStatus.FAILED, message=f"入库失败: {exc}")


async def run_chat(
    driver: Driver,
    store: RunStore,
    run_id: str,
    question: str,
) -> None:
    """问答后台任务（Agentic RAG）：通过 on_event 让 Agent 每步真实 emit 事件。

    优先调 answer_question_agentic（ReAct 循环），循环内每调一个工具就 emit 对应
    stage（vector_search→SEARCHING、expand_entity→LINKING、生成→WRITING），多轮问答
    会反复出现 SEARCHING/CHECKING，前端像素房间真正跟着 Agent 多轮决策走。
    降级：LLM 端点不支持 function calling 时，回退线性 answer_question，并按旧固定
    序列 emit 事件（searching→checking→writing），保证问答不挂、前端契约可预期。
    """
    try:
        answer = await _run_chat_agentic(driver, store, run_id, question)
    except Exception as exc:  # noqa: BLE001
        logger.exception("问答任务失败 run=%s", run_id)
        _emit(store, run_id, Stage.ERROR, RunStatus.FAILED, message=f"回答失败: {exc}")
        return

    _emit(
        store, run_id, Stage.IDLE, RunStatus.SUCCEEDED,
        message=f"回答完成（{len(answer.citations)} 条引用）",
        answer=answer.model_dump(by_alias=True),
    )


async def _run_chat_agentic(driver: Driver, store: RunStore, run_id: str, question: str):
    """跑 Agentic RAG；端点不支持 tool calling 时降级线性 pipeline。返回 Answer。

    answer_question_agentic 是同步且最重（多轮 LLM 调用），整个包进 asyncio.to_thread
    避免冻结事件循环。agent 在工作线程内通过 on_event 回调 emit 事件，RunStore 非线程
    安全，故用 loop.call_soon_threadsafe 把 emit 投递回事件循环线程执行。
    """
    loop = asyncio.get_running_loop()

    def _emit_cb(stage: Stage, message: str, **extra) -> None:
        # 工作线程内调用，通过 call_soon_threadsafe 把 append_event 调度回事件循环线程。
        # extra 携带 B12 可观测字段（tool_name/tool_input/tool_output），透传给 RunEvent。
        event = RunEvent(stage=stage, message=message, **extra)
        loop.call_soon_threadsafe(store.append_event, run_id, event)

    # B14：问答是最耗 LLM 的链路（多轮 ReAct），限并发防打爆 rate limit
    async with _LLM_SEMAPHORE:
        try:
            return await asyncio.to_thread(
                answer_question_agentic, driver, question, on_event=_emit_cb
            )
        except ToolCallingUnsupported as exc:
            logger.warning("LLM 不支持 tool calling，降级线性 RAG：%s", exc)
            _emit(store, run_id, Stage.SEARCHING, message="向量召回 + 重排 + 图谱扩展")
            _emit(store, run_id, Stage.CHECKING, message="组装上下文")
            _emit(store, run_id, Stage.WRITING, message="生成带引用回答")
            return await asyncio.to_thread(answer_question, driver, question)


async def run_delete(
    driver: Driver,
    store: RunStore,
    run_id: str,
    document_id: str,
) -> None:
    """删除后台任务：deleting→done，清理 Chunk/MENTIONS/RELATES/孤立 Entity/Document。

    实体若还被其它文档引用则保留（DETACH 只断开本文档的关系）。
    """
    try:
        _emit(store, run_id, Stage.DELETING, message=f"删除 {document_id}")
        # 两段 Cypher 逻辑上是一组（删 chunk/document + 清理孤立 entity），合并成一个
        # 同步 helper 整体丢进线程池，只创建一个工作线程。
        # Entity 没有直接连 Document，孤立性靠 MENTIONS 关系判定。
        await asyncio.to_thread(_do_delete, driver, document_id)
        _emit(store, run_id, Stage.IDLE, RunStatus.SUCCEEDED, message="删除完成")
    except Exception as exc:  # noqa: BLE001
        logger.exception("删除任务失败 run=%s", run_id)
        _emit(store, run_id, Stage.ERROR, RunStatus.FAILED, message=f"删除失败: {exc}")


def _do_delete(driver: Driver, document_id: str) -> None:
    """删除文档的同步 Cypher：先删 Chunk/Document，再清理孤立 Entity。"""
    driver.execute_query(
        """
        MATCH (d:Document {document_id: $document_id})
        OPTIONAL MATCH (d)-[:HAS_CHUNK]->(c:Chunk)
        DETACH DELETE c
        WITH d
        DETACH DELETE d
        """,
        document_id=document_id,
        database_="neo4j",
    )
    driver.execute_query(
        """
        MATCH (e:Entity)
        WHERE NOT (c:Chunk)-[:MENTIONS]->(e)
        DETACH DELETE e
        """,
        database_="neo4j",
    )
