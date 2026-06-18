"""parser 分派与 parse_file 组装：按扩展名选 parser，组装 ParsedDocument 并切块。"""

import os

from app.parsing.chunker import chunk_blocks
from app.parsing.errors import ParseError
from app.parsing.markdown_parser import parse_markdown
from app.parsing.models import ParsedDocument
from app.parsing.pdf_parser import parse_pdf
from app.parsing.text_parser import parse_text

SUPPORTED_EXTENSIONS: dict[str, str] = {
    ".txt": "text",
    ".md": "markdown",
    ".markdown": "markdown",
    ".pdf": "pdf",
}

_PARSERS = {
    "text": parse_text,
    "markdown": parse_markdown,
    "pdf": parse_pdf,
}


def parse_file(path: str, document_id: str | None = None) -> ParsedDocument:
    """解析单个文件为 ParsedDocument（含 chunks）。

    硬失败抛 ParseError：文件不存在 / 扩展名不支持。
    """
    if not os.path.isfile(path):
        raise ParseError(path=path, reason="文件不存在")

    ext = os.path.splitext(path)[1].lower()
    doc_type = SUPPORTED_EXTENSIONS.get(ext)
    if doc_type is None:
        raise ParseError(path=path, reason=f"不支持的扩展名: {ext}")

    doc_id = document_id or os.path.basename(path)
    raw_text, blocks = _PARSERS[doc_type](path)
    chunks = chunk_blocks(blocks, document_id=doc_id, raw_text=raw_text)
    return ParsedDocument(
        document_id=doc_id,
        source_path=path,
        doc_type=doc_type,
        raw_text=raw_text,
        chunks=chunks,
    )
