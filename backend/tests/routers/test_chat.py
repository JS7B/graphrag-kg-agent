"""chat 路由测试（B 板块：异步问答 + SSE 终态带 answer）。

POST /api/chat 改异步：返回 runId，后台 run_chat 跑检索+生成。
测试 mock run_chat 让它 emit 含 answer 的终态事件，验证响应契约 + SSE 终态带 answer。
chunk 反查（GET /api/chunks/{id}）走真实库。
"""

import pytest
from fastapi.testclient import TestClient

from app.clients.graph import get_driver
from app.main import create_app
from app.routers import chat as chat_mod
from app.runs import RunStore
from app.runs.models import RunEvent, RunStatus, Stage


async def _fake_run_chat(driver, store, run_id, question):
    """假问答任务：直接 emit 含 answer 的终态事件（方案 a）。"""
    store.append_event(
        run_id, RunEvent(stage=Stage.SEARCHING, status=RunStatus.RUNNING)
    )
    store.append_event(
        run_id, RunEvent(stage=Stage.CHECKING, status=RunStatus.RUNNING)
    )
    store.append_event(
        run_id,
        RunEvent(
            stage=Stage.IDLE,
            status=RunStatus.SUCCEEDED,
            answer={
                "question": question,
                "text": "mock answer [1]",
                "citations": [
                    {"chunkId": "c1", "index": 1, "text": "evidence"}
                ],
            },
        ),
    )


@pytest.fixture(autouse=True)
def _patch_run_chat(monkeypatch):
    monkeypatch.setattr(chat_mod, "run_chat", _fake_run_chat)


def _client():
    app = create_app()
    app.state.neo4j = get_driver()
    app.state.runs = RunStore()
    return TestClient(app), app


def test_chat_returns_run_id():
    client, _ = _client()
    resp = client.post("/api/chat", json={"question": "什么是 GraphRAG？"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "runId" in body


def test_chat_sse_terminal_event_carries_answer():
    """SSE 终态事件应带 answer 字段（前端方案 a，少一次往返）。"""
    client, _ = _client()
    run_id = client.post("/api/chat", json={"question": "test"}).json()["runId"]
    events = client.get(f"/api/runs/{run_id}/events").json()
    assert events[-1]["status"] == "succeeded"
    assert events[-1]["answer"]["text"] == "mock answer [1]"
    assert events[-1]["answer"]["citations"][0]["chunkId"] == "c1"
    stages = [e["stage"] for e in events]
    assert stages == ["searching", "checking", "idle"]


def test_chunk_lookup(ensured_schema):
    """GET /api/chunks/{id} 走真实库。"""
    ensured_schema.execute_query(
        """
        MERGE (d:Document {document_id: 'test_chunkdoc.md'})-[:HAS_CHUNK]->
              (c:Chunk {chunk_id: 'test_chunkdoc.md#0'})
          SET c.text='chunk body', c.page=1, c.char_start=0, c.char_end=10,
              c.heading_path=['H1'], c.document_id='test_chunkdoc.md'
        """,
        database_="neo4j",
    )
    client, _ = _client()
    r = client.get("/api/chunks/test_chunkdoc.md%230")
    assert r.status_code == 200
    body = r.json()
    assert body["chunkId"] == "test_chunkdoc.md#0"
    assert body["text"] == "chunk body"
