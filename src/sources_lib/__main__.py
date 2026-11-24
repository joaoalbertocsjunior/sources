"""Entry point: python -m sources_lib serve [options]

Starts an HTTPControlServer (REST + M2M JSON-RPC) so any language that can
spawn a subprocess and send HTTP POST can use sources-lib without Python imports.
"""
from __future__ import annotations

import argparse
import sys


def _serve(args: argparse.Namespace) -> None:
    from sources_lib import SourceRegistry
    from sources_lib.m2m import M2MServer
    from sources_lib.http import HTTPControlServer

    auth_fn = (lambda t: t == args.token) if args.token else None
    registry = SourceRegistry()

    if args.config:
        import json
        with open(args.config) as f:
            registry.load_config(json.load(f))

    m2m = M2MServer(auth_fn=auth_fn, registry=registry)
    server = HTTPControlServer(registry=registry, m2m=m2m, auth_fn=auth_fn)
    print(f"sources-lib serving on http://0.0.0.0:{args.port}", flush=True)
    server.start(host="0.0.0.0", port=args.port)


def main() -> None:
    parser = argparse.ArgumentParser(prog="sources-lib", description="sources-lib server")
    sub = parser.add_subparsers(dest="command", required=True)

    serve = sub.add_parser("serve", help="Start HTTP control + M2M server")
    serve.add_argument("--port", type=int, default=8080, help="Port to listen on (default: 8080)")
    serve.add_argument("--token", default=None, help="Bearer token for auth (omit to disable auth)")
    serve.add_argument("--config", default=None, help="Path to JSON config file for pre-loading sources")

    args = parser.parse_args()
    if args.command == "serve":
        _serve(args)


if __name__ == "__main__":
    main()
