"""Tests for DirectoryAdapter."""
from __future__ import annotations

import time

import pytest

from sources_lib.adapter import SourceRecord, SourceError, SourceUnavailableError, SourceActDeniedError
from sources_lib.adapters.directory import DirectoryAdapter


def _record(tmp_path, extra_config=None):
    config = {"path": str(tmp_path), **(extra_config or {})}
    return SourceRecord(id="test-dir", kind="directory", config=config, state={}, added_at=time.time())


# ── verify tests ──────────────────────────────────────────────────────────────

def test_verify_success(tmp_path):
    adapter = DirectoryAdapter()
    record = _record(tmp_path)
    result = adapter.verify(record, {})
    assert result["reachable"] is True
    assert result["is_dir"] is True
    assert "path" in result


def test_verify_missing_path_raises():
    adapter = DirectoryAdapter()
    record = SourceRecord(id="test-dir", kind="directory", config={}, state={}, added_at=time.time())
    with pytest.raises(SourceUnavailableError):
        adapter.verify(record, {})


def test_verify_nonexistent_raises(tmp_path):
    adapter = DirectoryAdapter()
    record = _record(tmp_path / "nope")
    with pytest.raises(SourceUnavailableError):
        adapter.verify(record, {})


def test_verify_file_not_dir_raises(tmp_path):
    f = tmp_path / "afile.txt"
    f.write_text("hello")
    adapter = DirectoryAdapter()
    record = SourceRecord(id="test-dir", kind="directory", config={"path": str(f)}, state={}, added_at=time.time())
    with pytest.raises(SourceUnavailableError):
        adapter.verify(record, {})


def test_verify_symlink_raises(tmp_path):
    real_dir = tmp_path / "real"
    real_dir.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real_dir)
    adapter = DirectoryAdapter()
    record = SourceRecord(id="test-dir", kind="directory", config={"path": str(link)}, state={}, added_at=time.time())
    with pytest.raises(SourceUnavailableError):
        adapter.verify(record, {})


# ── sync tests ────────────────────────────────────────────────────────────────

def test_sync_returns_entries(tmp_path):
    (tmp_path / "a.txt").write_text("aaa")
    (tmp_path / "b.txt").write_text("bbb")
    (tmp_path / "c.txt").write_text("ccc")
    (tmp_path / "subdir").mkdir()
    adapter = DirectoryAdapter()
    record = _record(tmp_path)
    rows = adapter.sync(record, {})
    assert len(rows) == 4
    names = {r["name"] for r in rows}
    assert names == {"a.txt", "b.txt", "c.txt", "subdir"}
    for row in rows:
        assert "name" in row
        assert "path" in row
        assert "kind" in row
        assert "size" in row
        assert "mtime" in row
        assert "source_id" in row
        assert row["source_id"] == "test-dir"
    kinds = {r["name"]: r["kind"] for r in rows}
    assert kinds["subdir"] == "dir"
    assert kinds["a.txt"] == "file"


def test_sync_skips_symlinks(tmp_path):
    (tmp_path / "real.txt").write_text("real")
    link = tmp_path / "link.txt"
    link.symlink_to(tmp_path / "real.txt")
    adapter = DirectoryAdapter()
    record = _record(tmp_path)
    rows = adapter.sync(record, {})
    names = {r["name"] for r in rows}
    assert "link.txt" not in names
    assert "real.txt" in names


def test_sync_skip_hidden(tmp_path):
    (tmp_path / ".hidden").write_text("hidden")
    (tmp_path / "visible").write_text("visible")
    adapter = DirectoryAdapter()
    record = _record(tmp_path, {"skip_hidden": True})
    rows = adapter.sync(record, {})
    names = {r["name"] for r in rows}
    assert "visible" in names
    assert ".hidden" not in names


def test_sync_hidden_included_by_default(tmp_path):
    (tmp_path / ".hidden").write_text("hidden")
    (tmp_path / "visible").write_text("visible")
    adapter = DirectoryAdapter()
    record = _record(tmp_path)
    rows = adapter.sync(record, {})
    names = {r["name"] for r in rows}
    assert "visible" in names
    assert ".hidden" in names


def test_sync_max_files_cap(tmp_path):
    for i in range(5):
        (tmp_path / f"file{i}.txt").write_text(f"content{i}")
    adapter = DirectoryAdapter(max_files=3)
    record = _record(tmp_path)
    rows = adapter.sync(record, {})
    assert len(rows) == 3


def test_sync_config_max_files_clamped(tmp_path):
    for i in range(5):
        (tmp_path / f"file{i}.txt").write_text(f"content{i}")
    adapter = DirectoryAdapter(max_files=3)
    record = _record(tmp_path)
    rows = adapter.sync(record, {"max_files": 10})
    assert len(rows) == 3


def test_sync_no_path_raises():
    adapter = DirectoryAdapter()
    record = SourceRecord(id="test-dir", kind="directory", config={}, state={}, added_at=time.time())
    with pytest.raises(SourceError):
        adapter.sync(record, {})


# ── act tests ─────────────────────────────────────────────────────────────────

def test_act_list(tmp_path):
    (tmp_path / "file1.txt").write_text("a")
    (tmp_path / "file2.txt").write_text("b")
    adapter = DirectoryAdapter()
    record = _record(tmp_path)
    result = adapter.act(record, {}, "list", {})
    assert "rows" in result
    assert "count" in result
    assert result["count"] == 2
    assert len(result["rows"]) == 2


def test_act_unsupported_raises(tmp_path):
    adapter = DirectoryAdapter()
    record = _record(tmp_path)
    with pytest.raises(SourceActDeniedError):
        adapter.act(record, {}, "delete", {})


def test_supported_actions(tmp_path):
    adapter = DirectoryAdapter()
    record = _record(tmp_path)
    assert adapter.supported_actions(record, {}) == ["list"]
