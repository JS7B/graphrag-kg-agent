"""parsing 包的自定义异常。"""


class ParseError(Exception):
    """硬失败：无法解析（文件不存在 / 扩展名不支持 / 文件损坏）。"""

    def __init__(self, path: str, reason: str) -> None:
        self.path = path
        self.reason = reason
        super().__init__(f"解析失败 [{path}]: {reason}")
