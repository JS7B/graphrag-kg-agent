"""应用配置：从仓库根 .env 读取，全部走环境变量，零硬编码密钥/地址/模型名。"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# 本文件位于 backend/app/config.py，仓库根为其上三级目录。
_REPO_ROOT = Path(__file__).resolve().parents[2]
_ENV_FILE = _REPO_ROOT / ".env"


class Settings(BaseSettings):
    """应用配置项。字段名 snake_case，环境变量名大小写不敏感。"""

    # LLM（OpenAI-compatible）
    # openai_* 给 embedding/rerank 用；chat 可单独走另一家（如 DeepSeek 官方）。
    # chat_base_url/chat_api_key 留空时回退 openai_*，保持单 provider 部署不破坏。
    openai_base_url: str = ""
    openai_api_key: str = ""
    chat_base_url: str = ""
    chat_api_key: str = ""
    chat_model: str = ""
    embedding_model: str = ""
    embedding_dim: int = 3072
    rerank_model: str = "bge-reranker-v2-m3"

    @property
    def effective_chat_base_url(self) -> str:
        """chat 实际使用的 base_url：优先 chat_base_url，留空回退 openai_base_url。"""
        return self.chat_base_url or self.openai_base_url

    @property
    def effective_chat_api_key(self) -> str:
        """chat 实际使用的 api_key：优先 chat_api_key，留空回退 openai_api_key。"""
        return self.chat_api_key or self.openai_api_key

    # Neo4j
    neo4j_uri: str = ""
    neo4j_username: str = ""
    neo4j_password: str = ""

    # 文档上传
    max_upload_mb: int = 10
    # PDF 页数上限（防 PDF 炸弹：超大 PDF 拖垮解析与抽取）
    max_pdf_pages: int = 200

    # API 鉴权（公开仓库防裸 curl）。为空则跳过校验，本地开发无感；部署时在 .env 配真实值启用。
    api_key: str = ""
    # CORS 允许来源（逗号分隔）。生产地址走 .env，默认仅本地前端。
    cors_origins: str = "http://localhost:5173"

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """获取全局唯一配置实例（带缓存，避免重复读取 .env）。"""
    return Settings()
