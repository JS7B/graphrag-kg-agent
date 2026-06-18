"""parsing 数据模型：SourceLocation / Block / Chunk / ParsedDocument。

所有偏移量相对 ParsedDocument.raw_text，左闭右开 [char_start, char_end)。
"""

from pydantic import BaseModel, Field


class SourceLocation(BaseModel):
    """一个 chunk 的来源位置（provenance）。"""

    document_id: str
    char_start: int
    char_end: int
    page: int | None = None
    heading_path: list[str] = Field(default_factory=list)


class Block(BaseModel):
    """parser 输出的中间语义块，喂给 chunker，不直接出库。"""

    text: str
    char_start: int
    char_end: int
    page: int | None = None
    heading_path: list[str] = Field(default_factory=list)


class Chunk(BaseModel):
    """本板块最终产物：带来源位置的文本片段。"""

    chunk_index: int
    text: str
    location: SourceLocation
    char_count: int


class ParsedDocument(BaseModel):
    """一次 parse_file 的完整结果。"""

    document_id: str
    source_path: str
    doc_type: str
    raw_text: str
    chunks: list[Chunk]
