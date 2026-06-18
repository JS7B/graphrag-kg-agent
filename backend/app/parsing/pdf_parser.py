"""PDF 解析（PyMuPDF）：逐页抽文本，记录跨页偏移与页码。

扫描版（无文本层）页只记 warning，不做 OCR。
"""

import logging
import re

import fitz

from app.parsing.errors import ParseError
from app.parsing.models import Block

logger = logging.getLogger(__name__)

_PARA_SPLIT = re.compile(r"\n[ \t]*\n")


def parse_pdf(path: str) -> tuple[str, list[Block]]:
    """读取 PDF，返回 (raw_text, blocks)。偏移相对拼接后的 raw_text。"""
    try:
        doc = fitz.open(path)
    except Exception as exc:  # PyMuPDF 抛 FileDataError 等
        raise ParseError(path=path, reason=f"无法打开 PDF: {exc}") from exc

    parts: list[str] = []
    blocks: list[Block] = []
    offset = 0
    try:
        for page_index in range(doc.page_count):
            page_no = page_index + 1
            page_text = doc[page_index].get_text("text")
            if page_text.strip() == "":
                logger.warning("PDF 第 %d 页无文本层（可能为扫描页）: %s", page_no, path)
            # 该页文本在 raw_text 中从 offset 开始
            for part in _PARA_SPLIT.split(page_text):
                if part.strip() == "":
                    continue
                stripped = part.strip()
                local = page_text.find(stripped)
                start = offset + local
                end = start + len(stripped)
                blocks.append(
                    Block(text=stripped, char_start=start, char_end=end, page=page_no)
                )
            parts.append(page_text)
            offset += len(page_text) + 1  # 页间插一个 \n
    finally:
        doc.close()

    raw_text = "\n".join(parts)
    return raw_text, blocks
