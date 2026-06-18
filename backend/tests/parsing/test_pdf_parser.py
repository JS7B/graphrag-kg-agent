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


def test_parse_pdf_duplicate_paragraphs_distinct_offsets(tmp_path):
    # 同一页含两个内容相同的段落：两段间插一个空白行元素，使 get_text 产出
    # "SAME\n \nSAME"，被空行正则切成两个相同 stripped 段。
    # 回归锁定：偏移定位必须用 pos 游标递进，否则第二段会错配到第一段位置。
    p = tmp_path / "dup.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 100), "SAME")
    page.insert_text((72, 130), " ")
    page.insert_text((72, 160), "SAME")
    doc.save(str(p))
    doc.close()

    raw, blocks = parse_pdf(str(p))
    same_blocks = [b for b in blocks if b.text == "SAME"]
    assert len(same_blocks) == 2
    # 两段偏移必须不同（bug 下会相同）
    assert same_blocks[0].char_start != same_blocks[1].char_start
    # 各自偏移都能切回正确文本
    for b in same_blocks:
        assert raw[b.char_start:b.char_end] == b.text


def test_parse_pdf_corrupt_raises(tmp_path):
    p = tmp_path / "bad.pdf"
    p.write_bytes(b"not a real pdf")
    with pytest.raises(ParseError):
        parse_pdf(str(p))
