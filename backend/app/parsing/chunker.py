"""chunker：把 Block 列表聚合成目标大小的 Chunk，保持同页同标题边界。

偏移与 text 一致性：chunk.text 一律取 raw_text[start:end]，保证
raw_text[chunk.char_start:chunk.char_end] == chunk.text。

注意：本模块假设输入 Block 已经 <= max_chars（超长预拆见 split_oversized_block，
由 Task 3 在调用前应用）。

不做小块回填：贪心聚合已用「适配 max_chars 且同页同标题」合并所有能合并的相邻块；
跨页/跨标题的微小尾块不回填（回填会污染 provenance），是 provenance 优先的有意产物。
"""

import logging

from app.parsing.models import Block, Chunk, SourceLocation

logger = logging.getLogger(__name__)

MAX_CHARS = 800
OVERLAP_CHARS = 150


def _make_chunk(index: int, group: list[Block], document_id: str, raw_text: str) -> Chunk:
    start = group[0].char_start
    end = group[-1].char_end
    text = raw_text[start:end]
    loc = SourceLocation(
        document_id=document_id,
        char_start=start,
        char_end=end,
        page=group[0].page,
        heading_path=group[0].heading_path,
    )
    return Chunk(chunk_index=index, text=text, location=loc, char_count=len(text))


def _same_boundary(a: Block, b: Block) -> bool:
    return a.page == b.page and a.heading_path == b.heading_path


def chunk_blocks(
    blocks: list[Block],
    document_id: str,
    raw_text: str,
    max_chars: int = MAX_CHARS,
    overlap_chars: int = OVERLAP_CHARS,
) -> list[Chunk]:
    """把 Block 列表聚合成 Chunk 列表。

    聚合：相邻块在「累积长度 + 下一块 <= max_chars」且同页同标题时合并进同一 chunk；
    否则收尾当前 chunk、另起一个。
    """
    if not blocks:
        return []

    groups: list[list[Block]] = []
    current: list[Block] = [blocks[0]]
    current_len = len(blocks[0].text)
    for block in blocks[1:]:
        fits = current_len + len(block.text) <= max_chars
        if fits and _same_boundary(current[-1], block):
            current.append(block)
            current_len += len(block.text)
        else:
            groups.append(current)
            current = [block]
            current_len = len(block.text)
    groups.append(current)

    return [
        _make_chunk(i, group, document_id, raw_text)
        for i, group in enumerate(groups)
    ]
