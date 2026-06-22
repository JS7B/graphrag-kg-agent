"""runs 测试夹具。

anyio 默认同时用 asyncio 和 trio 两个 backend 跑异步测试，但项目运行时只用
asyncio（FastAPI/uvicorn）。这里把 anyio_backend fixture 固定为 "asyncio"，
避免 trio 未安装时产生的虚假失败。
"""

import pytest


@pytest.fixture
def anyio_backend():
    return "asyncio"
