import time, threading, pytest
from sources.m2m import M2MServer, M2MClient, RpcError


def _start_server(dispatch_fn=None, auth_fn=None, port=17100):
    server = M2MServer(dispatch_fn=dispatch_fn, auth_fn=auth_fn)
    server.start(host="127.0.0.1", port=port)
    time.sleep(0.05)  # let it bind
    return server


def test_ping():
    s = _start_server(port=17101)
    try:
        result = s.handle("ping", {})
        assert result["pong"] is True
    finally:
        s.stop()


def test_dispatch_fn():
    def handle(method, params):
        if method == "echo":
            return params
        raise RpcError(-32601, "not found")
    s = _start_server(dispatch_fn=handle, port=17102)
    try:
        assert s.handle("echo", {"x": 1}) == {"x": 1}
    finally:
        s.stop()


def test_method_not_found_no_dispatch():
    s = _start_server(port=17103)
    try:
        with pytest.raises(RpcError) as exc_info:
            s.handle("nonexistent", {})
        assert exc_info.value.code == -32601
    finally:
        s.stop()


def test_jobs_submit_and_get():
    def slow(method, params):
        time.sleep(0.01)
        return {"done": True}
    s = _start_server(dispatch_fn=slow, port=17104)
    try:
        result = s.handle("jobs.submit", {"method": "slow", "params": {}})
        jid = result["id"]
        time.sleep(0.1)
        job = s.handle("jobs.get", {"id": jid})
        assert job["status"] == "done"
    finally:
        s.stop()


def test_jobs_list():
    s = _start_server(port=17105)
    try:
        s.handle("jobs.submit", {"method": "ping", "params": {}})
        jobs = s.handle("jobs.list", {})
        assert len(jobs) >= 1
    finally:
        s.stop()


def test_http_client_server_roundtrip():
    def handle(method, params):
        if method == "add":
            return {"sum": params["a"] + params["b"]}
        raise RpcError(-32601, "not found")
    s = _start_server(dispatch_fn=handle, port=17106)
    try:
        client = M2MClient("http://127.0.0.1:17106", token="")
        result = client.call("add", {"a": 3, "b": 4})
        assert result == {"sum": 7}
    finally:
        s.stop()


def test_auth_rejects_bad_token():
    s = _start_server(auth_fn=lambda t: t == "correct", port=17107)
    try:
        client = M2MClient("http://127.0.0.1:17107", token="wrong")
        with pytest.raises(Exception):
            client.call("ping", {})
    finally:
        s.stop()


def test_auth_admits_correct_token():
    s = _start_server(auth_fn=lambda t: t == "correct", port=17108)
    try:
        client = M2MClient("http://127.0.0.1:17108", token="correct")
        result = client.call("ping", {})
        assert result["pong"] is True
    finally:
        s.stop()
