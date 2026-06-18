"""目录导入：递归遍历，对支持的文件批量调 parse_file，单文件失败跳过。"""

import logging
import os

from app.parsing.base import SUPPORTED_EXTENSIONS, parse_file
from app.parsing.errors import ParseError
from app.parsing.models import ParsedDocument

logger = logging.getLogger(__name__)

_IGNORED_DIRS = {".git", "node_modules", "__pycache__", ".venv"}


def parse_directory(root: str) -> list[ParsedDocument]:
    """递归解析目录下所有支持的文件，返回 ParsedDocument 列表。"""
    docs: list[ParsedDocument] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _IGNORED_DIRS]
        for name in sorted(filenames):
            ext = os.path.splitext(name)[1].lower()
            if ext not in SUPPORTED_EXTENSIONS:
                continue
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            try:
                docs.append(parse_file(full, document_id=rel))
            except ParseError as exc:
                logger.error("跳过解析失败的文件 %s: %s", rel, exc)
    return docs
