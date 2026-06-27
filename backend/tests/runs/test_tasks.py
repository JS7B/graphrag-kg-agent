"""run_chat 后台任务单元测试：Agentic RAG 主路径 + 降级路径 + 失败路径。

run_chat 现在优先调 answer_question_agentic（on_event 真实 emit 每步事件），LLM
不支持 tool calling 时降级线性 answer_question（固定三事件序列）。三组用例分别覆盖。
不连真实 Neo4j/LLM，全 mock。
"""

import pytest

from app.qa.agent import ToolCallingUnsupported
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
async def test_run_chat_agentic_forwards_on_step_events(monkeypatch):
    """主路径：answer_question_agentic 经 on_event 发出逐步事件，run_chat 转发 + 终态 IDLE。"""

    def _agentic(driver, question, *, on_event=None, **kw):
        # 模拟 agent 循环内调用工具时经 on_event emit 的事件序列
        if on_event:
            on_event(Stage.SEARCHING, "向量检索")
            on_event(Stage.LINKING, "扩展实体关系")
            on_event(Stage.WRITING, "生成带引用回答")
        return _fake_answer()

    monkeypatch.setattr(tasks_mod, "answer_question_agentic", _agentic)
    store = RunStore()
    run = store.create_run(RunKind.CHAT)

    await tasks_mod.run_chat(driver=None, store=store, run_id=run.id, question="test")

    stages = [e.stage for e in run.events]
    # agent 逐步事件 + 终态 IDLE
    assert stages == [Stage.SEARCHING, Stage.LINKING, Stage.WRITING, Stage.IDLE]
    assert run.status == RunStatus.SUCCEEDED
    terminal = run.events[-1]
    assert terminal.answer is not None
    assert terminal.answer["text"] == "mock answer [1]"
    assert terminal.answer["citations"][0]["chunkId"] == "c1"


@pytest.mark.anyio
async def test_run_chat_falls_back_to_linear_on_unsupported_tools(monkeypatch):
    """降级路径：agent 抛 ToolCallingUnsupported 时回退线性版，发固定三事件 + 终态。"""

    def _unsupported(*a, **kw):
        raise ToolCallingUnsupported("tools not supported")

    monkeypatch.setattr(tasks_mod, "answer_question_agentic", _unsupported)
    monkeypatch.setattr(tasks_mod, "answer_question", _fake_answer)
    store = RunStore()
    run = store.create_run(RunKind.CHAT)

    await tasks_mod.run_chat(driver=None, store=store, run_id=run.id, question="test")

    stages = [e.stage for e in run.events]
    # 降级走旧固定序列（前端契约可预期）
    assert stages == [Stage.SEARCHING, Stage.CHECKING, Stage.WRITING, Stage.IDLE]
    assert run.status == RunStatus.SUCCEEDED
    assert run.events[-1].answer is not None


@pytest.mark.anyio
async def test_run_chat_failure_emits_error(monkeypatch):
    """失败路径：agent 抛普通异常时，run_chat emit error 终态（不吞异常）。"""

    def _boom(*a, **kw):
        raise RuntimeError("LLM down")

    monkeypatch.setattr(tasks_mod, "answer_question_agentic", _boom)
    store = RunStore()
    run = store.create_run(RunKind.CHAT)

    await tasks_mod.run_chat(driver=None, store=store, run_id=run.id, question="x")

    assert run.status == RunStatus.FAILED
    assert run.events[-1].stage == Stage.ERROR
    assert "LLM down" in run.events[-1].message
