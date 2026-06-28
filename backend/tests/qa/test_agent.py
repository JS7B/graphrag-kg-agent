"""Agentic RAG 集成测试：真实 LLM（function calling）+ 真 Neo4j。

验证 ReAct 循环的多轮决策、工具调用、引用可追溯、max_turns 终止、空证据兜底。
LLM 未配置则整体 skip（与 test_llm_real.py 同范式）。

检索部分（embed/search）用确定性 8 维向量（与 ensured_schema 的 TEST_DIM 对齐），
避免真实 embedding 的 3072 维与测试 schema 维度不匹配；LLM 的决策（chat_with_tools）
与生成（chat）走真实调用，这才是本测试要验证的 function calling 兼容性。
"""

import pytest

from app.clients.llm import is_configured
from app.graph.writer import ingest_document
from app.parsing.models import Chunk, ParsedDocument, SourceLocation
from app.qa import agent as agent_mod
from app.qa.agent import answer_question_agentic
from app.runs.models import Stage
from tests.conftest import TEST_DIM

pytestmark = pytest.mark.skipif(
    not is_configured(), reason="LLM 未配置，跳过真实 agent 测试"
)

DOC = "test_agent"

# 检索的文档内容——让"数据库/图谱"类问题能命中。
_RAW = "项目使用 Neo4j 作为知识图谱数据库，并用其向量索引做检索。"
_DOC_OBJ = ParsedDocument(
    document_id=DOC,
    source_path="test/agent.md",
    doc_type="markdown",
    raw_text=_RAW,
    chunks=[
        Chunk(
            chunk_index=0,
            text=_RAW,
            location=SourceLocation(document_id=DOC, char_start=0, char_end=len(_RAW)),
            char_count=len(_RAW),
        )
    ],
)


def _embed_vec():
    """固定的 8 维查询向量（与 seed 的 chunk 向量同方向，保证能召回）。"""
    return [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]


def _seed_and_patch(monkeypatch, ensured_schema):
    """seed 一篇带 8 维向量的文档 + monkeypatch llm.embed 返回 8 维（维度对齐 schema）。

    search_chunks 无需 patch：ensured_schema 把生产索引重建为 TEST_DIM=8，agent 默认查
    chunk_embedding 正好命中测试数据。
    """
    ingest_document(ensured_schema, _DOC_OBJ, [_embed_vec()], dim=TEST_DIM)
    monkeypatch.setattr(agent_mod.llm, "embed", lambda texts: [_embed_vec() for _ in texts])


def test_agent_multi_turn_with_citations(monkeypatch, ensured_schema):
    """需检索的问题：Agent 应调用 vector_search、生成带可追溯引用的答案。"""
    _seed_and_patch(monkeypatch, ensured_schema)

    answer = answer_question_agentic(ensured_schema, "项目用什么图谱数据库？")

    # 答案非空且带引用（引用可追溯红线：citation 必须来自真实检索）
    assert answer.text
    assert len(answer.citations) >= 1
    cited_chunk_ids = {c.chunk_id for c in answer.citations}
    assert all(cid.startswith(f"{DOC}#") for cid in cited_chunk_ids)


def test_agent_max_turns_terminates(monkeypatch, ensured_schema):
    """max_turns=1 极小上限：循环能正常终止，不抛异常、返回 Answer。"""
    _seed_and_patch(monkeypatch, ensured_schema)

    answer = answer_question_agentic(
        ensured_schema, "项目用什么图谱数据库？", max_turns=1
    )
    # 只要能正常返回 Answer 即说明 max_turns 兜底生效（未死循环、未抛错）
    assert answer.text
    assert answer.confidence in ("high", "medium", "low")


def test_agent_empty_evidence_answers_cannot_answer(monkeypatch, ensured_schema):
    """检索召回为空（问图库里没有的问题）：应回答「无法回答」、citations 为空。

    根因修正：原来用"正交向量"试图让向量召回为空，但 Neo4j 向量索引的 cosine
    检索总会返回 top-k 最近邻（相似度低也返回），无法靠正交制造空召回。改为直接
    mock search_chunks 返回空列表，这才是真正验证"空证据"场景。
    """
    monkeypatch.setattr(agent_mod, "search_chunks", lambda *a, **kw: [])

    answer = answer_question_agentic(ensured_schema, "木星有几颗卫星？")
    assert "无法回答" in answer.text
    assert answer.citations == []


def test_agent_on_event_emits_searching(monkeypatch, ensured_schema):
    """on_event 回调：调 vector_search 时应触发 SEARCHING stage（驱动前端动画）。"""
    _seed_and_patch(monkeypatch, ensured_schema)
    events: list[tuple[Stage, str]] = []

    answer_question_agentic(
        ensured_schema, "项目用什么图谱数据库？", on_event=lambda s, m: events.append((s, m))
    )

    stages = [s for s, _ in events]
    # 多轮问答至少应出现 SEARCHING（vector_search 触发）
    assert Stage.SEARCHING in stages
