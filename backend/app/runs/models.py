"""Run 与 RunEvent 数据模型 + Stage/Status 枚举。

Run 代表一次异步执行（入库/问答/删除），RunEvent 是执行过程中的进度信号。
Stage 枚举值与前端契约锁定（12 个），改动会破坏前端像素 Agent 状态机。
"""

import time
import uuid
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class Stage(str, Enum):
    """前端契约锁定的 12 个执行阶段。值即前端消费的字符串，不得改名。"""

    IDLE = "idle"
    UPLOADING = "uploading"
    PARSING = "parsing"
    EXTRACTING = "extracting"
    LINKING = "linking"
    INDEXING = "indexing"
    SEARCHING = "searching"
    CHECKING = "checking"
    WRITING = "writing"
    DELETING = "deleting"
    REBUILDING = "rebuilding"
    ERROR = "error"


class RunStatus(str, Enum):
    """Run 的整体生命周期状态。"""

    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class RunKind(str, Enum):
    """Run 的类型，决定前端走哪套进度展示。"""

    INGEST = "ingest"
    CHAT = "chat"
    DELETE = "delete"


class RunEvent(BaseModel):
    """单条进度事件，SSE 流的单位。answer 仅问答终态事件携带（方案 a）。"""

    model_config = ConfigDict(populate_by_name=True)

    stage: Stage
    status: RunStatus = RunStatus.RUNNING
    message: str = ""
    answer: dict | None = None
    timestamp_ms: int = Field(
        default_factory=lambda: int(time.time() * 1000), alias="timestampMs"
    )


class Run(BaseModel):
    """一次异步执行的完整记录：固定元数据 + 有序事件流。"""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(alias="runId", default_factory=lambda: uuid.uuid4().hex[:12])
    kind: RunKind
    status: RunStatus = RunStatus.RUNNING
    created_at: int = Field(
        alias="createdAt", default_factory=lambda: int(time.time() * 1000)
    )
    events: list[RunEvent] = Field(default_factory=list)

    @property
    def is_terminal(self) -> bool:
        """是否进入终态（成功或失败），终态后 SSE 流应关闭。"""
        return self.status in (RunStatus.SUCCEEDED, RunStatus.FAILED)

    @property
    def current_stage(self) -> Stage:
        """最近一个事件的 stage，无事件时为 idle。"""
        return self.events[-1].stage if self.events else Stage.IDLE
