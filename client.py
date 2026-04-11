

"""Minimal API client for interacting with the Bug Triage OpenEnv server."""

from __future__ import annotations

import json
from typing import Any, Optional
from urllib import error, request

from models import ActionModel


class EnvClient:
    """Small HTTP client for reset/step/state calls."""

    def __init__(self, base_url: str = "http://127.0.0.1:7860") -> None:
        self.base_url = base_url.rstrip("/")

    def _url(self, path: str) -> str:
        return f"{self.base_url}/{path.lstrip('/')}"

    def _request(
        self,
        method: str,
        path: str,
        payload: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        body = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"

        req = request.Request(
            url=self._url(path),
            data=body,
            headers=headers,
            method=method.upper(),
        )
        try:
            with request.urlopen(req, timeout=30) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"HTTP {exc.code} {exc.reason}: {details}") from exc

    def reset(self, task_id: Optional[str] = None, seed: Optional[int] = None) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if task_id is not None:
            payload["task_id"] = task_id
        if seed is not None:
            payload["seed"] = seed
        return self._request("POST", "/reset", payload if payload else None)

    def step(self, action: ActionModel) -> dict[str, Any]:
        return self._request(
            "POST",
            "/step",
            {"action": action.model_dump(mode="json", exclude_none=True)},
        )

    def state(self) -> dict[str, Any]:
        return self._request("GET", "/state")

    def tasks(self) -> dict[str, Any]:
        return self._request("GET", "/tasks")

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/health")
