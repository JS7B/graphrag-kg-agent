"""后台任务：把入库/问答/删除的同步链路包成「带进度事件」的异步执行单元。

FastAPI BackgroundTasks 在事件循环线程跑——入库链路是同步代码会短暂阻塞事件循环，
但个人项目单用户场景可接受（后续如需可包 starlette.concurrency.run_in_threadpool）。

每个任务全程 try/except：BackgroundTasks 会吞掉异常，失败必须自己 emit error +
run.status=failed，否则前端 SSE 流永不关闭、像素 Agent 卡在中间状态。
"""

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
            doc = parse_file(tmp_path, document_id=source_name)
        finally:
            try:
                os.remove(tmp_path)
            except OSError:
                pass

        _emit(store, run_id, Stage.EXTRACTING, message="生成向量并写入图库")
        embeddings = embed_chunks(doc)
        ingest_document(driver, doc, embeddings, name=source_name, source_type=doc_type)

        _emit(store, run_id, Stage.INDEXING, message="抽取实体与关系")
        stats = extract_and_ingest(driver, doc)

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
        answer = _run_chat_agentic(driver, store, run_id, question)
    except Exception as exc:  # noqa: BLE001
        logger.exception("问答任务失败 run=%s", run_id)
        _emit(store, run_id, Stage.ERROR, RunStatus.FAILED, message=f"回答失败: {exc}")
        return

    _emit(
        store, run_id, Stage.IDLE, RunStatus.SUCCEEDED,
        message=f"回答完成（{len(answer.citations)} 条引用）",
        answer=answer.model_dump(by_alias=True),
    )


def _run_chat_agentic(driver: Driver, store: RunStore, run_id: str, question: str):
    """跑 Agentic RAG；端点不支持 tool calling 时降级线性 pipeline。返回 Answer。"""
    try:
        def _emit_cb(stage: Stage, message: str) -> None:
            _emit(store, run_id, stage, message=message)

        return answer_question_agentic(driver, question, on_event=_emit_cb)
    except ToolCallingUnsupported as exc:
        logger.warning("LLM 不支持 tool calling，降级线性 RAG：%s", exc)
        _emit(store, run_id, Stage.SEARCHING, message="向量召回 + 重排 + 图谱扩展")
        _emit(store, run_id, Stage.CHECKING, message="组装上下文")
        _emit(store, run_id, Stage.WRITING, message="生成带引用回答")
        return answer_question(driver, question)


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
        # 先删本文档的所有 Chunk（及其 MENTIONS 关系），再删 Document，
        # 最后清理因本文档删除而变成「无任何 chunk 指向」的孤立 Entity。
        # Entity 没有直接连 Document，孤立性靠 MENTIONS 关系判定。
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
        _emit(store, run_id, Stage.IDLE, RunStatus.SUCCEEDED, message="删除完成")
    except Exception as exc:  # noqa: BLE001
        logger.exception("删除任务失败 run=%s", run_id)
        _emit(store, run_id, Stage.ERROR, RunStatus.FAILED, message=f"删除失败: {exc}")
