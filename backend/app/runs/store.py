"""进程内 Run 注册表：存历史 + 支持 SSE 订阅。

不持久化：重启后 Run/Event 丢失。Run 是瞬态进度信号，前端刷新会重新查
Document 状态（落 Neo4j），丢失 Run 进度可接受。符合 CLAUDE.md「简单优先」。

订阅用 asyncio.Queue：每个订阅者一个队列，append_event 时向所有队列投递事件副本。
终态事件（status=succeeded/failed）后，is_terminal 让订阅者知道流该关闭。
"""

import asyncio

from app.runs.models import Run, RunEvent, RunKind, RunStatus, Stage


class RunStore:
    def __init__(self) -> None:
        self._runs: dict[str, Run] = {}
        self._subscribers: dict[str, list[asyncio.Queue]] = {}

    def create_run(self, kind: RunKind) -> Run:
        run = Run(kind=kind)
        self._runs[run.id] = run
        self._subscribers[run.id] = []
        return run

    def get_run(self, run_id: str) -> Run | None:
        return self._runs.get(run_id)

    def append_event(self, run_id: str, event: RunEvent) -> None:
        """记录事件到历史，并向所有订阅者投递副本。Run 终态即随事件更新。"""
        run = self._runs.get(run_id)
        if run is None:
            raise KeyError(f"Run 不存在: {run_id}")
        run.events.append(event)
        if event.status in (RunStatus.SUCCEEDED, RunStatus.FAILED):
            run.status = event.status
        for queue in self._subscribers.get(run_id, []):
            queue.put_nowait(event)

    def events(self, run_id: str) -> list[RunEvent]:
        return list(self._runs[run_id].events) if run_id in self._runs else []

    async def subscribe(self, run_id: str) -> asyncio.Queue:
        """订阅一个 Run 的新事件。调用方从 queue.get() 取事件，is_terminal 后退出。"""
        if run_id not in self._runs:
            raise KeyError(f"Run 不存在: {run_id}")
        queue: asyncio.Queue = asyncio.Queue()
        # 先投递历史事件，保证订阅者不漏掉 append 在 subscribe 之前的事件。
        for event in self._runs[run_id].events:
            queue.put_nowait(event)
        self._subscribers[run_id].append(queue)
        return queue

    def unsubscribe(self, run_id: str, queue: asyncio.Queue) -> None:
        subs = self._subscribers.get(run_id, [])
        if queue in subs:
            subs.remove(queue)
