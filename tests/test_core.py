import pytest
from sources import (
    BaseSourceAdapter, SourceRecord, SourceRegistry, EventEmitter,
    LocalTransport, TransportError, SchemaError, validate_schema,
    SourceActDeniedError,
)


# ── Adapter / Registry ──────────────────────────────────────────────────────

class EchoAdapter(BaseSourceAdapter):
    config_schema = {
        "type": "object",
        "required": ["message"],
        "properties": {"message": {"type": "string"}},
    }
    actions = ["ping"]

    def sync(self, record, config):
        return [{"echo": record.config["message"]}]

    def act(self, record, config, action, payload):
        super().act(record, config, action, payload)
        return {"pong": True}


def test_register_and_add():
    reg = SourceRegistry()
    reg.register_kind("echo", EchoAdapter())
    rec = reg.add("echo", source_id="e1", config={"message": "hello"})
    assert rec.id == "e1"
    assert rec.kind == "echo"


def test_sync():
    reg = SourceRegistry()
    reg.register_kind("echo", EchoAdapter())
    reg.add("echo", source_id="e1", config={"message": "hi"})
    rows = reg.sync("e1")
    assert rows == [{"echo": "hi"}]


def test_act_valid():
    reg = SourceRegistry()
    reg.register_kind("echo", EchoAdapter())
    reg.add("echo", source_id="e1", config={"message": "hi"})
    result = reg.act("e1", "ping")
    assert result == {"pong": True}


def test_act_invalid_raises():
    reg = SourceRegistry()
    reg.register_kind("echo", EchoAdapter())
    reg.add("echo", source_id="e1", config={"message": "hi"})
    with pytest.raises(SourceActDeniedError):
        reg.act("e1", "unknown")


def test_schema_validation_on_add():
    reg = SourceRegistry()
    reg.register_kind("echo", EchoAdapter())
    with pytest.raises(Exception):
        reg.add("echo", config={"wrong": "field"})


def test_duplicate_source_id():
    from sources.registry import RegistryError
    reg = SourceRegistry()
    reg.register_kind("echo", EchoAdapter())
    reg.add("echo", source_id="e1", config={"message": "a"})
    with pytest.raises(RegistryError):
        reg.add("echo", source_id="e1", config={"message": "b"})


# ── EventEmitter ─────────────────────────────────────────────────────────────

def test_event_emit_and_receive():
    emitter = EventEmitter()
    received = []
    emitter.on("test.event", lambda event, **kw: received.append(kw))
    emitter.emit("test.event", value=42)
    assert received == [{"value": 42}]


def test_event_off():
    emitter = EventEmitter()
    received = []
    handler = lambda event, **kw: received.append(kw)
    emitter.on("x", handler)
    emitter.off("x", handler)
    emitter.emit("x", value=1)
    assert received == []


def test_handler_exception_does_not_propagate():
    emitter = EventEmitter()
    emitter.on("x", lambda event, **kw: 1 / 0)
    emitter.emit("x")  # must not raise


# ── Schema ───────────────────────────────────────────────────────────────────

def test_validate_schema_pass():
    validate_schema({"name": "alice"}, {"type": "object", "required": ["name"]})


def test_validate_schema_fail():
    with pytest.raises(SchemaError):
        validate_schema({"other": "x"}, {"type": "object", "required": ["name"]})


def test_validate_empty_schema_always_passes():
    validate_schema({"anything": True}, {})


# ── LocalTransport ───────────────────────────────────────────────────────────

def test_local_transport_json(tmp_path):
    import json
    p = tmp_path / "data.json"
    p.write_text(json.dumps([{"a": 1}, {"a": 2}]))
    t = LocalTransport()
    rows = t.read(str(p))
    assert rows == [{"a": 1}, {"a": 2}]


def test_local_transport_csv(tmp_path):
    p = tmp_path / "data.csv"
    p.write_text("name,val\nalice,1\nbob,2\n")
    t = LocalTransport()
    rows = t.read(str(p))
    assert len(rows) == 2
    assert rows[0]["name"] == "alice"


def test_local_transport_missing_file():
    t = LocalTransport()
    assert t.read("/nonexistent/file.json") == []


def test_local_transport_verify():
    t = LocalTransport()
    assert not t.verify("/nonexistent.json")


def test_local_transport_write_csv(tmp_path):
    p = tmp_path / "out.csv"
    t = LocalTransport()
    n = t.write(str(p), [{"x": "1"}, {"x": "2"}])
    assert n == 2
    rows = t.read(str(p))
    assert len(rows) == 2


def test_local_transport_sqlite(tmp_path):
    p = tmp_path / "db.sqlite"
    connect = f"sqlite:///{p}"
    t = LocalTransport()
    t.write(connect, [{"col": "val1"}, {"col": "val2"}], table="items")
    rows = t.read(connect, table="items")
    assert len(rows) == 2
