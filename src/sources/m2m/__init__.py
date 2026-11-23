"""M2M — JSON-RPC 2.0 machine-to-machine interface."""
from .interface import M2MServer, M2MClient, RpcError, JobModel, TaskResult

__all__ = ["M2MServer", "M2MClient", "RpcError", "JobModel", "TaskResult"]
