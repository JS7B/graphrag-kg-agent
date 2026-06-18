"""base 分派与 parse_file 组装测试。"""

import pytest

from app.parsing.base import parse_file
from app.parsing.errors import ParseError


def test_parse_file_txt(tmp_path):
    p = tmp_path / "doc.txt"
    p.write_text("第一段。\n\n第二段。", encoding="utf-8")
    doc = parse_file(str(p))
    assert doc.doc_type == "text"
    assert doc.document_id == "doc.txt"
    assert len(doc.chunks) >= 1


def test_parse_file_markdown(tmp_path):
    p = tmp_path / "doc.md"
    p.write_text("# 标题\n\n正文内容。", encoding="utf-8")
    doc = parse_file(str(p))
    assert doc.doc_type == "markdown"


def test_parse_file_chunk_offsets_traceable(tmp_path):
    p = tmp_path / "doc.txt"
    p.write_text("AAA\n\nBBB", encoding="utf-8")
    doc = parse_file(str(p))
    for c in doc.chunks:
        assert doc.raw_text[c.location.char_start:c.location.char_end] == c.text


def test_parse_file_custom_document_id(tmp_path):
    p = tmp_path / "doc.txt"
    p.write_text("内容", encoding="utf-8")
    doc = parse_file(str(p), document_id="custom-id")
    assert doc.document_id == "custom-id"
    assert all(c.location.document_id == "custom-id" for c in doc.chunks)


def test_parse_file_missing_raises():
    with pytest.raises(ParseError):
        parse_file("/nonexistent/path/x.txt")


def test_parse_file_unsupported_extension_raises(tmp_path):
    p = tmp_path / "doc.xyz"
    p.write_text("内容", encoding="utf-8")
    with pytest.raises(ParseError):
        parse_file(str(p))
