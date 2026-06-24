"""run_chat 后台任务单元测试：验证修复后正确调用 answer_question。

之前 run_chat 有 bug（question 没先 embed 就传 search_chunks + Answer 塞不存在的
question 字段）。修复后改为复用 answer_question。这里 mock answer_question，
验证 run_chat 在各里程碑 emit 正确事件序列 + 终态带 answer。
不连真实 Neo4j/LLM。
"""

import pytest

from app.qa.models import Answer, Citation
from app.runs import RunStore
from app.runs import tasks as tasks_mod
from app.runs.models import RunKind, RunStatus, Stage


def _fake_answer(*args, **kwargs):
    return Answer(
        text="mock answer [1]",
        confidence="medium",
        citations=[Citation(index=1, chunk_id="c1", document_id="d1", location="loc", snippet="evi")],
    )


@pytest.mark.anyio
async def test_run_chat_emits_full_event_sequence(monkeypatch):
    """run_chat 应 emit searching→checking→writing→done，终态带 answer。"""
    monkeypatch.setattr(tasks_mod, "answer_question", _fake_answer)
    store = RunStore()
    run = store.create_run(RunKind.CHAT)

    await tasks_mod.run_chat(driver=None, store=store, run_id=run.id, question="test")

    stages = [e.stage for e in run.events]
    assert stages == [Stage.SEARCHING, Stage.CHECKING, Stage.WRITING, Stage.IDLE]
    assert run.status == RunStatus.SUCCEEDED
    # 终态事件带 answer
    terminal = run.events[-1]
    assert terminal.answer is not None
    assert terminal.answer["text"] == "mock answer [1]"
    assert terminal.answer["citations"][0]["chunkId"] == "c1"


@pytest.mark.anyio
async def test_run_chat_failure_emits_error(monkeypatch):
    """answer_question 抛异常时，run_chat 应 emit error 终态（不吞异常）。"""

    def _boom(*a, **kw):
        raise RuntimeError("LLM down")

    monkeypatch.setattr(tasks_mod, "answer_question", _boom)
    store = RunStore()
    run = store.create_run(RunKind.CHAT)

    await tasks_mod.run_chat(driver=None, store=store, run_id=run.id, question="x")

    assert run.status == RunStatus.FAILED
    assert run.events[-1].stage == Stage.ERROR
    assert "LLM down" in run.events[-1].message
