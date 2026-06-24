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
    """问答后台任务：searching→checking→writing→done，终态事件带 answer（方案 a）。

    直接复用已验证正确的 answer_question（同步链路），在各里程碑 emit 事件让前端
    像素 Agent 跟着真实检索进度走。不拆步骤手写——曾因 search_chunks 误传 question
    字符串（应先 embed）+ Answer 构造了不存在的 question 字段而出 bug，复用正确实现
    更稳妥。
    """
    try:
        _emit(store, run_id, Stage.SEARCHING, message="向量召回 + 重排 + 图谱扩展")
        _emit(store, run_id, Stage.CHECKING, message="组装上下文")
        _emit(store, run_id, Stage.WRITING, message="生成带引用回答")

        answer = answer_question(driver, question)

        _emit(
            store, run_id, Stage.IDLE, RunStatus.SUCCEEDED,
            message=f"回答完成（{len(answer.citations)} 条引用）",
            answer=answer.model_dump(by_alias=True),
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("问答任务失败 run=%s", run_id)
        _emit(store, run_id, Stage.ERROR, RunStatus.FAILED, message=f"回答失败: {exc}")


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
