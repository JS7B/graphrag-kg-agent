"""文档库路由：上传入库（同步链路）、列表、单文档详情。

A 板块（文档上传/入库 API）：POST 同步跑完整链路返回结果摘要；GET 直接查 Neo4j
Document 节点（写入时已落状态字段）。响应用 camelCase alias，与 chat 路由风格一致。
"""

import os

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, UploadFile
from pydantic import BaseModel, ConfigDict, Field

from app.config import get_settings
from app.runs.models import RunKind
from app.runs.tasks import run_delete, run_ingest

router = APIRouter(prefix="/api", tags=["documents"])

# 支持的上传扩展名 → doc_type 映射（doc_type 喂给 parse_file 决定走哪个 parser）。
_SUPPORTED = {".md": "markdown", ".txt": "txt", ".pdf": "pdf"}


# ── 响应模型（camelCase alias 对齐前端契约，populate_by_name 便于内部构造）──

_RESPONSE_CONFIG = ConfigDict(populate_by_name=True)


class IngestResponse(BaseModel):
    """异步上传响应：立即返回 runId + documentId，前端订阅 SSE 拿入库进度。"""

    model_config = _RESPONSE_CONFIG

    run_id: str = Field(alias="runId")
    document_id: str = Field(alias="documentId")
    document_name: str = Field(alias="documentName")


class DeleteResponse(BaseModel):
    """异步删除响应。"""

    model_config = _RESPONSE_CONFIG

    run_id: str = Field(alias="runId")
    document_id: str = Field(alias="documentId")


class DocumentMeta(BaseModel):
    """前端 DocumentMeta：id/name/sourceType/parseStatus/indexStatus/chunkCount。"""

    model_config = _RESPONSE_CONFIG

    document_id: str = Field(alias="id")
    name: str
    source_type: str = Field(alias="sourceType")
    parse_status: str = Field(alias="parseStatus")
    index_status: str = Field(alias="indexStatus")
    chunk_count: int = Field(alias="chunkCount")


# ── Cypher：查 Document 节点（直接读写入时落的状态字段）──

_LIST_DOCS = """
MATCH (d:Document)
RETURN d.document_id AS document_id, d.name AS name, d.source_type AS source_type,
       d.parse_status AS parse_status, d.index_status AS index_status,
       d.chunk_count AS chunk_count
ORDER BY d.name
"""

_GET_DOC = """
MATCH (d:Document {document_id: $document_id})
RETURN d.document_id AS document_id, d.name AS name, d.source_type AS source_type,
       d.parse_status AS parse_status, d.index_status AS index_status,
       d.chunk_count AS chunk_count
"""


def _row_to_meta(row: dict) -> dict:
    """把 Cypher 行转成 DocumentMeta 的 camelCase dict。"""
    return DocumentMeta(
        document_id=row["document_id"],
        name=row["name"] or "",
        source_type=row["source_type"] or "",
        parse_status=row["parse_status"] or "pending",
        index_status=row["index_status"] or "pending",
        chunk_count=row["chunk_count"] or 0,
    ).model_dump(by_alias=True)


@router.post("/documents")
async def upload_document(
    request: Request, background_tasks: BackgroundTasks, file: UploadFile
) -> dict:
    """上传单文件并起后台入库任务（异步）。立即返回 runId + documentId。

    B 板块：上传改为异步——校验通过后把文件字节交给 BackgroundTasks 跑 run_ingest，
    前端用 runId 订阅 SSE 拿入库进度（uploading→parsing→extracting→indexing→done）。
    document_id 用源文件名预生成，保证 chunk_id 幂等，前端可立即用它查进度。
    """
    settings = get_settings()
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in _SUPPORTED:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型: {ext or '(无扩展名)'}，仅支持 {sorted(_SUPPORTED)}",
        )

    content = await file.read()
    if len(content) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail=f"文件过大({len(content)}字节)，上限 {settings.max_upload_mb}MB",
        )

    store = request.app.state.runs
    driver = request.app.state.neo4j
    source_name = os.path.basename(file.filename or "upload")

    run = store.create_run(RunKind.INGEST)
    background_tasks.add_task(
        run_ingest, driver, store, run.id, content, source_name, _SUPPORTED[ext]
    )

    return IngestResponse(
        run_id=run.id,
        document_id=source_name,
        document_name=source_name,
    ).model_dump(by_alias=True)


@router.get("/documents")
async def list_documents(request: Request) -> list[dict]:
    """列出所有文档及其状态（直接查 Document 节点）。"""
    driver = request.app.state.neo4j
    records, _, _ = driver.execute_query(_LIST_DOCS, database_="neo4j")
    return [_row_to_meta(r.data()) for r in records]


@router.get("/documents/{document_id}")
async def get_document(request: Request, document_id: str) -> dict:
    """取单个文档详情。"""
    driver = request.app.state.neo4j
    records, _, _ = driver.execute_query(
        _GET_DOC, document_id=document_id, database_="neo4j"
    )
    if not records:
        raise HTTPException(status_code=404, detail=f"文档不存在: {document_id}")
    return _row_to_meta(records[0].data())


@router.delete("/documents/{document_id}")
async def delete_document(
    request: Request,
    background_tasks: BackgroundTasks,
    document_id: str,
) -> dict:
    """删除文档（异步）：起后台任务清理 Chunk/MENTIONS/RELATES/孤立 Entity/Document。

    立即返回 runId，前端订阅 SSE 拿删除进度（deleting→done）。
    文档不存在也返回 runId（后台任务 DETACH DELETE 对空集是 no-op，简单优先）。
    """
    store = request.app.state.runs
    driver = request.app.state.neo4j
    run = store.create_run(RunKind.DELETE)
    background_tasks.add_task(run_delete, driver, store, run.id, document_id)
    return DeleteResponse(run_id=run.id, document_id=document_id).model_dump(by_alias=True)
