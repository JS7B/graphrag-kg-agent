"""embedding 编排：把文本批量转成向量。

embed_texts 是通用版本（任意文本列表）；embed_chunks 是它的文档特化封装，
保留与 chunk 严格同序的约定。复用 clients.llm.embed（OpenAI-compatible）。
"""

from app.clients import llm
from app.config import get_settings
from app.parsing.models import ParsedDocument


def embed_texts(texts: list[str], *, batch_size: int = 64) -> list[list[float]]:
    """对任意文本列表批量生成向量，返回与输入同序的向量列表。

    分批仅为绕开 embedding API 的单请求条数/token 上限，不影响顺序。
    首向量维度校验：若与 EMBEDDING_DIM 配置不符立即抛错，避免维度错误延迟到
    写入/查询才暴露（L6 同类症状：换模型忘改 EMBEDDING_DIM）。
    """
    embeddings: list[list[float]] = []
    for start in range(0, len(texts), batch_size):
        embeddings.extend(llm.embed(texts[start : start + batch_size]))

    if embeddings:
        expected = get_settings().embedding_dim
        actual = len(embeddings[0])
        if actual != expected:
            raise ValueError(
                f"embedding 维度 {actual} 与配置 EMBEDDING_DIM={expected} 不符，"
                f"请检查 EMBEDDING_MODEL 与 EMBEDDING_DIM 是否一致"
            )
    return embeddings


def embed_chunks(doc: ParsedDocument, *, batch_size: int = 64) -> list[list[float]]:
    """对文档所有 chunk 文本生成向量，返回与 doc.chunks 同序的向量列表。"""
    return embed_texts([chunk.text for chunk in doc.chunks], batch_size=batch_size)
