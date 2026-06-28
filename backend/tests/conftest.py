"""顶层共享测试夹具：Neo4j 探测 / 测试维度 schema / 数据清理。

graph / extraction / qa 三个板块的集成测试共用这套夹具（pytest 自动向上查找
conftest，子目录无需重复定义）。

向量索引维度的关键约定（教训 L6）：
向量索引名固定（CHUNK_VECTOR_INDEX，与生产同名），是**全库共享单例**，不像
test_ 前缀节点能靠 autouse 清理隔离。测试为加速用 TEST_DIM=8 重建它，**必须在
session 结束时恢复成生产维度（EMBEDDING_DIM）**——否则 8 维残留会让真实问答的
3072 维查询撞维度报错（db.index.vector.queryNodes: dimensions mismatch）。
"""

import pytest

from app.clients.graph import close, get_driver, verify_connectivity
from app.config import get_settings
from app.graph.schema import CHUNK_VECTOR_INDEX, ensure_schema

# 集成测试用的小维度：合成向量短、跑得快。生产维度走 EMBEDDING_DIM（如 3072）。
TEST_DIM = 8


@pytest.fixture(scope="session")
def neo4j_driver():
    """连真实 Neo4j 容器；连不上则跳过所有集成测试。"""
    driver = get_driver()
    try:
        verify_connectivity(driver)
    except Exception:
        close(driver)
        pytest.skip("Neo4j 不可用，跳过集成测试")
    yield driver
    close(driver)


@pytest.fixture(scope="session")
def ensured_schema(neo4j_driver):
    """以测试维度（TEST_DIM）重建向量索引；session 结束恢复成生产维度。

    teardown 恢复是关键：向量索引是全库共享单例，不恢复会污染后续真实查询（L6）。
    """
    # setup：DROP 后以测试维度重建，确保索引维度 = TEST_DIM
    neo4j_driver.execute_query(
        f"DROP INDEX {CHUNK_VECTOR_INDEX} IF EXISTS", database_="neo4j"
    )
    ensure_schema(neo4j_driver, dim=TEST_DIM)

    yield neo4j_driver

    # teardown：恢复成生产维度（EMBEDDING_DIM），避免 8 维残留污染真实查询
    prod_dim = get_settings().embedding_dim
    neo4j_driver.execute_query(
        f"DROP INDEX {CHUNK_VECTOR_INDEX} IF EXISTS", database_="neo4j"
    )
    ensure_schema(neo4j_driver, dim=prod_dim)


@pytest.fixture(autouse=True)
def _clean(neo4j_driver):
    """每个测试后清理 test_ 前缀的节点（含其关系），不污染共享库。"""
    yield
    neo4j_driver.execute_query(
        "MATCH (n) WHERE n.document_id STARTS WITH 'test_' DETACH DELETE n",
        database_="neo4j",
    )


@pytest.fixture(autouse=True)
def _disable_api_key_auth():
    """测试统一禁用 API Key 鉴权，避免本地 .env 配了真实 API_KEY 时 TestClient 裸调 401。

    鉴权是部署层关注点，测试不验证它（鉴权逻辑由 middleware.py 自身保证）。
    get_settings() 是 lru_cache 单例，改实例属性即全局生效。
    """
    get_settings().api_key = ""
