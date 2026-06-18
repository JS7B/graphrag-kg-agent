"""pdf_parser 测试：页码、跨页偏移、损坏文件。fixture 用 fitz 现生成。"""

import fitz
import pytest

from app.parsing.pdf_parser import parse_pdf
from app.parsing.errors import ParseError


def _make_pdf(path, pages):
    doc = fitz.open()
    for text in pages:
        page = doc.new_page()
        page.insert_text((72, 72), text)
    doc.save(str(path))
    doc.close()


def test_parse_pdf_two_pages_with_page_numbers(tmp_path):
    p = tmp_path / "a.pdf"
    _make_pdf(p, ["第一页内容", "第二页内容"])
    raw, blocks = parse_pdf(str(p))
    pages = {b.page for b in blocks}
    assert pages == {1, 2}


def test_parse_pdf_raw_text_contains_both_pages(tmp_path):
    p = tmp_path / "a.pdf"
    _make_pdf(p, ["AAAA", "BBBB"])
    raw, blocks = parse_pdf(str(p))
    assert "AAAA" in raw
    assert "BBBB" in raw


def test_parse_pdf_offsets_traceable(tmp_path):
    p = tmp_path / "a.pdf"
    _make_pdf(p, ["AAAA", "BBBB"])
    raw, blocks = parse_pdf(str(p))
    for b in blocks:
        assert raw[b.char_start:b.char_end] == b.text


def test_parse_pdf_corrupt_raises(tmp_path):
    p = tmp_path / "bad.pdf"
    p.write_bytes(b"not a real pdf")
    with pytest.raises(ParseError):
        parse_pdf(str(p))
