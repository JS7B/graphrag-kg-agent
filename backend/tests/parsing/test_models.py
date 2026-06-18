"""parsing 数据模型与异常的基础测试。"""

import pytest

from app.parsing.models import Block, Chunk, ParsedDocument, SourceLocation
from app.parsing.errors import ParseError


def test_source_location_defaults():
    loc = SourceLocation(document_id="doc1", char_start=0, char_end=10)
    assert loc.page is None
    assert loc.heading_path == []


def test_block_holds_offsets_and_provenance():
    block = Block(text="hello", char_start=3, char_end=8, page=2, heading_path=["A", "B"])
    assert block.char_end - block.char_start == 5
    assert block.page == 2
    assert block.heading_path == ["A", "B"]


def test_chunk_carries_location():
    loc = SourceLocation(document_id="doc1", char_start=0, char_end=5, page=1)
    chunk = Chunk(chunk_index=0, text="hello", location=loc, char_count=5)
    assert chunk.chunk_index == 0
    assert chunk.location.page == 1


def test_parsed_document_holds_chunks():
    doc = ParsedDocument(
        document_id="doc1",
        source_path="/tmp/doc1.txt",
        doc_type="text",
        raw_text="hello world",
        chunks=[],
    )
    assert doc.doc_type == "text"
    assert doc.chunks == []


def test_parse_error_message_contains_path_and_reason():
    err = ParseError(path="/tmp/bad.xyz", reason="unsupported extension")
    assert "/tmp/bad.xyz" in str(err)
    assert "unsupported extension" in str(err)
