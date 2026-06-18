"""chunker 测试：聚合、同页同标题守卫、小块回填、偏移可追溯。"""

from app.parsing.chunker import chunk_blocks, MAX_CHARS
from app.parsing.models import Block


def _block(text, start, page=None, heading=None):
    return Block(
        text=text,
        char_start=start,
        char_end=start + len(text),
        page=page,
        heading_path=heading or [],
    )


def test_small_adjacent_blocks_merge_into_one_chunk():
    raw = "AAA\n\nBBB"
    blocks = [_block("AAA", 0), _block("BBB", 5)]
    chunks = chunk_blocks(blocks, document_id="d", raw_text=raw)
    assert len(chunks) == 1
    assert chunks[0].location.char_start == 0
    assert chunks[0].location.char_end == 8
    assert chunks[0].text == raw[0:8]


def test_offset_is_traceable_to_raw_text():
    raw = "AAA\n\nBBB"
    blocks = [_block("AAA", 0), _block("BBB", 5)]
    chunks = chunk_blocks(blocks, document_id="d", raw_text=raw)
    for c in chunks:
        assert raw[c.location.char_start:c.location.char_end] == c.text


def test_different_page_does_not_merge():
    raw = "AAA\n\nBBB"
    blocks = [_block("AAA", 0, page=1), _block("BBB", 5, page=2)]
    chunks = chunk_blocks(blocks, document_id="d", raw_text=raw)
    assert len(chunks) == 2
    assert chunks[0].location.page == 1
    assert chunks[1].location.page == 2


def test_different_heading_does_not_merge():
    raw = "AAA\n\nBBB"
    blocks = [_block("AAA", 0, heading=["X"]), _block("BBB", 5, heading=["Y"])]
    chunks = chunk_blocks(blocks, document_id="d", raw_text=raw)
    assert len(chunks) == 2


def test_chunk_index_is_sequential():
    raw = "AAA\n\nBBB"
    blocks = [_block("AAA", 0, page=1), _block("BBB", 5, page=2)]
    chunks = chunk_blocks(blocks, document_id="d", raw_text=raw)
    assert [c.chunk_index for c in chunks] == [0, 1]


def test_small_trailing_block_same_boundary_merges():
    # 同页同标题、合计 <= max_chars 的尾块在聚合阶段就并入，不另起 chunk
    raw = "A" * 700 + "\n\n" + "B" * 10
    blocks = [_block("A" * 700, 0), _block("B" * 10, 702)]
    chunks = chunk_blocks(blocks, document_id="d", raw_text=raw)
    assert len(chunks) == 1
    assert chunks[0].location.char_end == 712


def test_small_trailing_block_cross_boundary_stays_separate():
    # 跨页的微小尾块不回填，保留为独立小 chunk（provenance 优先的有意产物）
    raw = "A" * 700 + "\n\n" + "B" * 10
    blocks = [_block("A" * 700, 0, page=1), _block("B" * 10, 702, page=2)]
    chunks = chunk_blocks(blocks, document_id="d", raw_text=raw)
    assert len(chunks) == 2
    assert chunks[1].location.page == 2


def test_empty_blocks_returns_empty():
    assert chunk_blocks([], document_id="d", raw_text="") == []
