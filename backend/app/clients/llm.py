"""OpenAI-compatible LLM 薄封装：chat / embedding / rerank，以及配置状态探测。"""

import httpx
from openai import OpenAI
from openai.types.chat import ChatCompletionMessage

from app.config import get_settings

# 占位值标记：.env.example 里的 sk-your-key-here / https://your-provider 这类未填真实值。
_PLACEHOLDER_MARKERS = ("your-", "please-change")


def _client() -> OpenAI:
    settings = get_settings()
    return OpenAI(
        base_url=settings.openai_base_url,
        api_key=settings.openai_api_key,
        # 默认无超时会让偶发网络卡顿拖死整个请求（httpx 默认 600s）；
        # 60s 总超时 + 10s 连接超时对 chat/embed 够用，重试交给 SDK。
        timeout=httpx.Timeout(60, connect=10),
        max_retries=3,
    )


def is_configured() -> bool:
    """判断 LLM 是否已配置真实值（非空且不含占位标记）。"""
    settings = get_settings()
    base_url = settings.openai_base_url
    api_key = settings.openai_api_key
    if not base_url or not api_key:
        return False
    combined = f"{base_url} {api_key}".lower()
    return not any(marker in combined for marker in _PLACEHOLDER_MARKERS)


def chat(messages: list[dict], *, response_format: dict | None = None) -> str:
    """调用 chat completion，返回首条回复文本。

    response_format 透传给 OpenAI-compatible 端点（如 {"type": "json_object"} 开启 JSON 模式）；
    缺省 None 时行为与原先完全一致。
    """
    settings = get_settings()
    kwargs: dict = {"model": settings.chat_model, "messages": messages}
    if response_format is not None:
        kwargs["response_format"] = response_format
    resp = _client().chat.completions.create(**kwargs)
    # 部分兼容端点在异常输入下可能返回空 choices，直接取 [0] 会 IndexError。
    if not resp.choices:
        raise RuntimeError("LLM 返回空 choices，可能是模型或输入异常")
    return resp.choices[0].message.content or ""


def chat_with_tools(
    messages: list[dict],
    *,
    tools: list[dict],
    tool_choice: str = "auto",
) -> ChatCompletionMessage:
    """带 function calling 的 chat completion，返回完整 message 对象。

    与 chat() 的区别：透传 tools / tool_choice，返回 ChatCompletionMessage（含
    tool_calls + content），由调用方（agent.py）读取 .tool_calls 决定后续编排。
    端点不支持 tools 时会抛 openai.BadRequestError，由 agent 层捕获触发降级。
    """
    settings = get_settings()
    resp = _client().chat.completions.create(
        model=settings.chat_model,
        messages=messages,
        tools=tools,
        tool_choice=tool_choice,
    )
    if not resp.choices:
        raise RuntimeError("LLM 返回空 choices，可能是模型或输入异常")
    return resp.choices[0].message


def embed(texts: list[str]) -> list[list[float]]:
    """对文本列表生成向量。"""
    settings = get_settings()
    resp = _client().embeddings.create(
        model=settings.embedding_model,
        input=texts,
    )
    if not resp.data:
        raise RuntimeError("LLM embedding 返回空 data，可能是模型或输入异常")
    return [item.embedding for item in resp.data]


def rerank(
    query: str, documents: list[str], *, top_n: int | None = None
) -> list[tuple[int, float]]:
    """对文档按与 query 的相关性重排，返回 [(原始索引, 相关性分数)] 降序。

    OpenAI SDK 无 rerank 端点，直接 POST {base_url}/rerank。documents 为空时返回空列表。
    """
    if not documents:
        return []
    settings = get_settings()
    payload: dict = {
        "model": settings.rerank_model,
        "query": query,
        "documents": documents,
    }
    if top_n is not None:
        payload["top_n"] = top_n
    resp = httpx.post(
        f"{settings.openai_base_url.rstrip('/')}/rerank",
        headers={"Authorization": f"Bearer {settings.openai_api_key}"},
        json=payload,
        timeout=60,
    )
    resp.raise_for_status()
    results = resp.json()["results"]
    return [(item["index"], item["relevance_score"]) for item in results]
