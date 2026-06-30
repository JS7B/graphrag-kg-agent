"""问答 API 集成（B 板块：异步 chat + chunk 反查）。

POST /api/chat 改异步：返回 runId，后台 run_chat 跑检索+生成（契约由 test_chat.py
覆盖）。本文件聚焦真实 chunk 反查（GET /api/chunks/{id}）走真实库；chat 异步契约
此处也补一条真实 seed 驱动的验证，mock run_chat 发 emit 含 answer 的终态事件。
"""

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.runs import RunStore
from app.runs.models import RunEvent, RunStatus, Stage

DOC = "test_qa_doc"


def _seed_graph(driver):
    """写入 2 个 chunk + 实体 + 关系（8 维占位向量，匹配测试索引）。"""
    driver.execute_query(
        """
        MERGE (d:Document {document_id: $doc}) SET d.source_path = 'qa/doc.md'
        MERGE (c0:Chunk {chunk_id: $c0})
          SET c0.document_id=$doc, c0.text=$t0, c0.chunk_index=0,
              c0.char_start=0, c0.char_end=40, c0.heading_path=['GraphRAG 系统'],
              c0.embedding=$vec
        MERGE (c1:Chunk {chunk_id: $c1})
          SET c1.document_id=$doc, c1.text=$t1, c1.chunk_index=1,
              c1.char_start=40, c1.char_end=80, c1.heading_path=['GraphRAG 系统'],
              c1.embedding=$vec
        MERGE (d)-[:HAS_CHUNK]->(c0)
        MERGE (d)-[:HAS_CHUNK]->(c1)
        MERGE (e1:Entity {entity_id: $e1}) SET e1.name='GraphRAG', e1.document_id=$doc
        MERGE (e2:Entity {entity_id: $e2}) SET e2.name='Neo4j', e2.document_id=$doc
        MERGE (c0)-[:MENTIONS]->(e1)
        MERGE (c0)-[:MENTIONS]->(e2)
        MERGE (e1)-[:RELATES {type:'依赖', evidence_chunk_id:$c0}]->(e2)
        """,
        doc=DOC, c0=f"{DOC}#0", c1=f"{DOC}#1",
        t0="GraphRAG 依赖 Neo4j 存储知识图谱，使用向量检索召回相关片段。",
        t1="FastAPI 提供后端接口，Pydantic 负责数据校验。",
        vec=[0.1] * 8, e1=f"{DOC}::graphrag::技术概念", e2=f"{DOC}::neo4j::产品模块",
        database_="neo4j",
    )


def _client(driver):
    """构造 TestClient 并注入测试 driver + RunStore（不走 lifespan）。"""
    app = create_app()
    app.state.neo4j = driver
    app.state.runs = RunStore()
    return TestClient(app), app


def test_chat_returns_run_id_with_seed(monkeypatch, ensured_schema):
    """B 板块：chat 异步返回 runId；mock run_chat emit 含 answer 的终态事件。

    原同步测试（monkeypatch answer_question）已失效——chat 改异步后由 run_chat 后台
    执行。这里保留真实 seed + 真实 chunk 反查的价值，mock run_chat 验证 SSE 终态带 answer。
    """
    _seed_graph(ensured_schema)

    async def _fake_run_chat(driver, store, run_id, question, conversation_id):
        store.append_event(
            run_id, RunEvent(stage=Stage.SEARCHING, status=RunStatus.RUNNING)
        )
        store.append_event(
            run_id,
            RunEvent(
                stage=Stage.IDLE,
                status=RunStatus.SUCCEEDED,
                answer={
                    "question": question,
                    "text": "GraphRAG 用 Neo4j 存储知识图谱 [1]",
                    "citations": [{"chunkId": f"{DOC}#0", "index": 1}],
                },
            ),
        )

    from app.conversations import Conversation
    from app.routers import chat as chat_mod

    monkeypatch.setattr(chat_mod, "run_chat", _fake_run_chat)
    # mock create_conversation 避免真连库建会话污染
    monkeypatch.setattr(
        chat_mod, "create_conversation",
        lambda driver, *, title="新会话": Conversation(conversation_id="conv_test_seed", title=title),
    )
    client, _ = _client(ensured_schema)
    resp = client.post("/api/chat", json={"question": "用什么存储知识图谱？"})
    assert resp.status_code == 200
    run_id = resp.json()["runId"]
    events = client.get(f"/api/runs/{run_id}/events").json()
    assert events[-1]["status"] == "succeeded"
    assert events[-1]["answer"]["text"]
    assert events[-1]["answer"]["citations"][0]["chunkId"] == f"{DOC}#0"


def test_get_chunk_returns_text(ensured_schema):
    _seed_graph(ensured_schema)
    client, _ = _client(ensured_schema)
    resp = client.get(f"/api/chunks/{DOC}%230")  # %23 = '#'
    assert resp.status_code == 200
    body = resp.json()
    assert body["chunkId"] == f"{DOC}#0"
    assert body["documentName"] == "qa/doc.md"
    assert "Neo4j" in body["text"]
    assert "GraphRAG 系统" in body["location"]


def test_get_missing_chunk_404(ensured_schema):
    client, _ = _client(ensured_schema)
    resp = client.get("/api/chunks/test_qa_doc%23999")
    assert resp.status_code == 404
