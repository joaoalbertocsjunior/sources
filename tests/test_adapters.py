import json, os, pytest, tempfile, pathlib
from sources.adapters import FileAdapter, ShellAdapter, EnvAdapter, DatabaseAdapter, HttpPollAdapter
from sources import SourceRegistry, SourceRecord


def _reg(kind, adapter, config):
    reg = SourceRegistry()
    reg.register_kind(kind, adapter)
    reg.add(kind, source_id="s1", config=config)
    return reg


# FileAdapter
def test_file_adapter_sync(tmp_path):
    p = tmp_path / "test.txt"
    p.write_text("hello world")
    reg = _reg("file", FileAdapter(), {"path": str(p)})
    rows = reg.sync("s1")
    assert rows[0]["content"] == "hello world"

def test_file_adapter_missing():
    reg = _reg("file", FileAdapter(), {"path": "/nonexistent/file.txt"})
    assert reg.sync("s1") == []

def test_file_adapter_verify(tmp_path):
    p = tmp_path / "f.txt"; p.write_text("x")
    reg = _reg("file", FileAdapter(), {"path": str(p)})
    result = reg.verify("s1")
    assert result["ok"] is True

# ShellAdapter
def test_shell_adapter_sync():
    reg = _reg("shell", ShellAdapter(), {"command": "echo hello"})
    rows = reg.sync("s1")
    assert "hello" in rows[0]["stdout"]

def test_shell_adapter_returncode():
    reg = _reg("shell", ShellAdapter(), {"command": "true"})
    rows = reg.sync("s1")
    assert rows[0]["returncode"] == 0

# EnvAdapter
def test_env_adapter_prefix():
    os.environ["TESTPFX_FOO"] = "bar"
    reg = _reg("env", EnvAdapter(), {"prefix": "TESTPFX_"})
    rows = reg.sync("s1")
    keys = {r["key"] for r in rows}
    assert "TESTPFX_FOO" in keys

def test_env_adapter_redact():
    os.environ["SECRET_KEY"] = "s3cr3t"
    reg = _reg("env", EnvAdapter(), {"keys": ["SECRET_KEY"], "redact": ["SECRET_KEY"]})
    rows = reg.sync("s1")
    assert rows[0]["value"] == "***"

# DatabaseAdapter
def test_database_adapter_sqlite(tmp_path):
    import sqlite3
    db = tmp_path / "test.db"
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE items (name TEXT)")
    conn.execute("INSERT INTO items VALUES ('alice')")
    conn.commit(); conn.close()
    reg = _reg("db", DatabaseAdapter(), {
        "connect": str(db), "table": "items", "driver": "sqlite3"
    })
    rows = reg.sync("s1")
    assert any(r["name"] == "alice" for r in rows)

# HttpPollAdapter — test with a mock
def test_http_poll_adapter_verify_bad_url():
    from sources import SourceUnavailableError
    reg = _reg("http", HttpPollAdapter(), {"url": "http://127.0.0.1:19999/nonexistent"})
    result = reg.verify("s1")
    assert result["ok"] is False
