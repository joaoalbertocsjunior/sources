import json, time, threading, urllib.request, pytest
from sources import SourceRegistry, HTTPControlServer
from sources.m2m import M2MServer
from sources.adapters import FileAdapter


BASE = "http://127.0.0.1"


def _get(port, path, token=""):
    req = urllib.request.Request(
        f"{BASE}:{port}{path}",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(req, timeout=5) as r:
        return json.loads(r.read()), r.status


def _post(port, path, body=None, token=""):
    data = json.dumps(body or {}).encode()
    req = urllib.request.Request(
        f"{BASE}:{port}{path}",
        data=data,
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {token}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=5) as r:
        return json.loads(r.read()), r.status


def _start(port, registry=None, m2m=None, auth_fn=None):
    ctrl = HTTPControlServer(registry=registry, m2m=m2m, auth_fn=auth_fn)
    ctrl.start(port=port)
    time.sleep(0.05)
    return ctrl


def test_health(tmp_path):
    ctrl = _start(18200)
    try:
        data, status = _get(18200, "/health")
        assert status == 200
        assert data["ok"] is True
    finally:
        ctrl.stop()


def test_sources_list_empty(tmp_path):
    ctrl = _start(18201)
    try:
        data, status = _get(18201, "/sources")
        assert status == 200
        assert data == []
    finally:
        ctrl.stop()


def test_sources_kinds(tmp_path):
    reg = SourceRegistry()
    reg.register_kind("file", FileAdapter())
    ctrl = _start(18202, registry=reg)
    try:
        data, status = _get(18202, "/sources/kinds")
        assert "file" in data
    finally:
        ctrl.stop()


def test_register_and_sync_source(tmp_path):
    p = tmp_path / "data.txt"
    p.write_text("hello")
    reg = SourceRegistry()
    reg.register_kind("file", FileAdapter())
    ctrl = _start(18203, registry=reg)
    try:
        # Register via POST /sources
        data, status = _post(18203, "/sources",
                              {"kind": "file", "id": "f1",
                               "config": {"path": str(p)}})
        assert status == 201
        # Sync via POST /sources/f1/sync
        data, status = _post(18203, "/sources/f1/sync")
        assert data["count"] == 1
        assert "hello" in data["rows"][0]["content"]
    finally:
        ctrl.stop()


def test_verify_source(tmp_path):
    p = tmp_path / "v.txt"
    p.write_text("x")
    reg = SourceRegistry()
    reg.register_kind("file", FileAdapter())
    reg.add("file", source_id="v1", config={"path": str(p)})
    ctrl = _start(18204, registry=reg)
    try:
        data, status = _post(18204, "/sources/v1/verify")
        assert data["ok"] is True
    finally:
        ctrl.stop()


def test_rpc_passthrough(tmp_path):
    m2m = M2MServer()
    ctrl = _start(18205, m2m=m2m)
    try:
        data, status = _post(18205, "/rpc",
                              {"jsonrpc": "2.0", "method": "ping",
                               "params": {}, "id": "1"})
        assert data["result"]["pong"] is True
    finally:
        ctrl.stop()


def test_jobs_list(tmp_path):
    m2m = M2MServer()
    ctrl = _start(18206, m2m=m2m)
    try:
        data, status = _get(18206, "/jobs")
        assert isinstance(data, list)
    finally:
        ctrl.stop()


def test_auth_rejects(tmp_path):
    ctrl = _start(18207, auth_fn=lambda t: t == "secret")
    try:
        from urllib.error import HTTPError
        with pytest.raises(HTTPError) as exc_info:
            _get(18207, "/health", token="wrong")
        assert exc_info.value.code == 401
    finally:
        ctrl.stop()


def test_auth_admits(tmp_path):
    ctrl = _start(18208, auth_fn=lambda t: t == "secret")
    try:
        data, status = _get(18208, "/health", token="secret")
        assert status == 200
    finally:
        ctrl.stop()
