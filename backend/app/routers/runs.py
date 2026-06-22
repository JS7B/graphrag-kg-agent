"""Run 进度路由：SSE 实时流、历史事件兜底、Run 概况。

SSE 流订阅 RunStore 队列，每个 RunEvent 即推即发；Run 进入终态（succeeded/failed）
后发完最后一条事件即关闭流，前端据此停止 EventSource。
"""

import asyncio
import json

from fastapi import APIRouter, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from app.runs.models import RunStatus

router = APIRouter(prefix="/api/runs", tags=["runs"])

# 订阅等待新事件的最长间隔：Run 终态后会立即关闭，此超时只是防御性兜底。
_POLL_TIMEOUT = 60.0


def _get_store(request: Request):
    store = getattr(request.app.state, "runs", None)
    if store is None:
        raise HTTPException(status_code=503, detail="Run 服务未就绪")
    return store


def _event_to_payload(event) -> dict:
    """RunEvent → SSE data 字段（JSON 字符串前端 JSON.parse）。"""
    data = event.model_dump(by_alias=True)
    data["stage"] = event.stage.value  # str Enum 序列化成纯字符串
    data["status"] = event.status.value
    return data


@router.get("/{run_id}/events/stream")
async def stream_events(request: Request, run_id: str):
    """SSE 流：先投递历史事件，再实时推送新事件，终态后关闭。"""
    store = _get_store(request)
    run = store.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run 不存在: {run_id}")

    async def event_generator():
        queue = await store.subscribe(run_id)
        try:
            while True:
                # 取已有/新事件；超时则发心跳让连接保活。
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=_POLL_TIMEOUT)
                except asyncio.TimeoutError:
                    yield {"event": "ping", "data": ""}
                    continue
                yield {"event": "message", "data": json.dumps(_event_to_payload(event))}
                if event.status in (RunStatus.SUCCEEDED, RunStatus.FAILED):
                    break
        finally:
            store.unsubscribe(run_id, queue)

    return EventSourceResponse(event_generator())


@router.get("/{run_id}/events")
async def list_events(request: Request, run_id: str):
    """历史事件兜底：客户端断线重连时一次性取回全部事件。"""
    store = _get_store(request)
    run = store.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run 不存在: {run_id}")
    return [_event_to_payload(e) for e in store.events(run_id)]


@router.get("/{run_id}")
async def get_run(request: Request, run_id: str):
    """Run 概况：状态、当前阶段、事件数、类型、创建时间。"""
    store = _get_store(request)
    run = store.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run 不存在: {run_id}")
    return {
        "runId": run.id,
        "kind": run.kind.value,
        "status": run.status.value,
        "currentStage": run.current_stage.value,
        "eventCount": len(run.events),
        "createdAt": run.created_at,
    }
