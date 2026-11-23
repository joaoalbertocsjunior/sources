"""GitHub adapter — list issues, PRs, commits or file contents (requires sources-lib[github])."""
from __future__ import annotations

import time
from typing import Any

from ..adapter import BaseSourceAdapter, SourceRecord, SourceActDeniedError, SourceUnavailableError, SourceError

try:
    from github import Github as _Github, GithubException as _GithubException
    _GITHUB_AVAILABLE = True
except ImportError:
    _Github = None  # type: ignore[assignment,misc]
    _GithubException = None  # type: ignore[assignment]
    _GITHUB_AVAILABLE = False


class GitHubAdapter(BaseSourceAdapter):
    """List GitHub repo resources (issues, PRs, commits, contents) as source rows."""

    config_schema = {
        "type": "object",
        "required": ["repo"],
        "properties": {
            "repo": {"type": "string", "description": "owner/repo"},
            "token": {"type": "string"},
            "resource": {
                "type": "string",
                "enum": ["issues", "pulls", "commits", "contents"],
                "default": "issues",
            },
            "state": {"type": "string", "enum": ["open", "closed", "all"], "default": "open"},
            "path": {"type": "string", "description": "file path for resource=contents"},
            "limit": {"type": "integer", "default": 100},
        },
    }
    actions = ["create_issue", "close_issue", "create_comment"]

    def _client(self, record: SourceRecord, config: dict[str, Any]):
        if not _GITHUB_AVAILABLE:
            raise SourceUnavailableError("sources-lib[github] required: pip install sources-lib[github]")
        token = record.config.get("token") or config.get("github_token", "")
        return _Github(token or None)

    def verify(self, record: SourceRecord, config: dict[str, Any]) -> dict[str, Any]:
        gh = self._client(record, config)
        try:
            repo = gh.get_repo(record.config["repo"])
            return {"ok": True, "repo": repo.full_name, "private": repo.private}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def sync(self, record: SourceRecord, config: dict[str, Any]) -> list[dict[str, Any]]:
        gh = self._client(record, config)
        resource = record.config.get("resource", "issues")
        limit = record.config.get("limit", 100)
        try:
            repo = gh.get_repo(record.config["repo"])
            if resource == "issues":
                state = record.config.get("state", "open")
                items = list(repo.get_issues(state=state)[:limit])
                return [{"number": i.number, "title": i.title, "state": i.state,
                         "url": i.html_url, "created_at": str(i.created_at),
                         "source_id": record.id, "observed_at": time.time()} for i in items]
            elif resource == "pulls":
                state = record.config.get("state", "open")
                items = list(repo.get_pulls(state=state)[:limit])
                return [{"number": p.number, "title": p.title, "state": p.state,
                         "url": p.html_url, "created_at": str(p.created_at),
                         "source_id": record.id, "observed_at": time.time()} for p in items]
            elif resource == "commits":
                items = list(repo.get_commits()[:limit])
                return [{"sha": c.sha[:12], "message": c.commit.message.splitlines()[0],
                         "author": c.commit.author.name, "date": str(c.commit.author.date),
                         "url": c.html_url, "source_id": record.id,
                         "observed_at": time.time()} for c in items]
            elif resource == "contents":
                path = record.config.get("path", "")
                contents = repo.get_contents(path)
                if not isinstance(contents, list):
                    contents = [contents]
                return [{"name": c.name, "path": c.path, "type": c.type, "size": c.size,
                         "sha": c.sha, "url": c.html_url, "source_id": record.id,
                         "observed_at": time.time()} for c in contents]
            else:
                raise SourceError(f"Unknown resource: {resource}")
        except (SourceError, SourceUnavailableError):
            raise
        except Exception as exc:
            raise SourceError(str(exc)) from exc

    def act(self, record: SourceRecord, config: dict[str, Any],
            action: str, payload: dict[str, Any]) -> dict[str, Any]:
        if action not in self.actions:
            raise SourceActDeniedError(f"Unsupported action: {action}")
        gh = self._client(record, config)
        try:
            repo = gh.get_repo(record.config["repo"])
            if action == "create_issue":
                issue = repo.create_issue(
                    title=payload.get("title", ""),
                    body=payload.get("body", ""),
                    labels=payload.get("labels", []),
                )
                return {"number": issue.number, "url": issue.html_url}
            elif action == "close_issue":
                issue = repo.get_issue(number=payload["number"])
                issue.edit(state="closed")
                return {"number": issue.number, "state": "closed"}
            elif action == "create_comment":
                issue = repo.get_issue(number=payload["number"])
                comment = issue.create_comment(payload.get("body", ""))
                return {"id": comment.id, "url": comment.html_url}
        except (SourceActDeniedError, SourceUnavailableError):
            raise
        except Exception as exc:
            raise SourceError(str(exc)) from exc
        return {}
