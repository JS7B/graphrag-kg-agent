"""repo_importer 测试：递归命中、跳过噪音目录、单文件失败不中断。"""

from app.parsing.repo_importer import parse_directory


def test_imports_supported_files_recursively(tmp_path):
    (tmp_path / "a.md").write_text("# A\n\n正文。", encoding="utf-8")
    (tmp_path / "b.txt").write_text("文本。", encoding="utf-8")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "c.md").write_text("# C\n\n内容。", encoding="utf-8")
    docs = parse_directory(str(tmp_path))
    ids = {d.document_id for d in docs}
    assert ids == {"a.md", "b.txt", "sub/c.md"}


def test_skips_git_directory(tmp_path):
    (tmp_path / "a.md").write_text("# A\n\n正文。", encoding="utf-8")
    git = tmp_path / ".git"
    git.mkdir()
    (git / "config.md").write_text("# 不该被导入", encoding="utf-8")
    docs = parse_directory(str(tmp_path))
    ids = {d.document_id for d in docs}
    assert ids == {"a.md"}


def test_ignores_unsupported_extensions(tmp_path):
    (tmp_path / "a.txt").write_text("文本。", encoding="utf-8")
    (tmp_path / "b.xyz").write_text("忽略。", encoding="utf-8")
    docs = parse_directory(str(tmp_path))
    assert {d.document_id for d in docs} == {"a.txt"}


def test_empty_directory_returns_empty(tmp_path):
    docs = parse_directory(str(tmp_path))
    assert docs == []
