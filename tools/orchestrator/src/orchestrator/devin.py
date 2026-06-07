"""Devin v3 session API client."""
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any

import requests


DEFAULT_BASE_URL = "https://api.devin.ai/v3"

_TERMINAL_STATUSES = frozenset(
    {"exit", "suspended", "stopped", "blocked", "completed", "error", "failed"}
)


@dataclass(frozen=True)
class Session:
    session_id: str
    url: str
    status: str
    status_detail: str | None
    acus_consumed: float
    pull_requests: list[dict]
    structured_output: dict | None
    tags: list[str]
    raw: dict


class DevinClient:
    def __init__(self, *, api_key: str, org_id: str, base_url: str = DEFAULT_BASE_URL) -> None:
        self.api_key = api_key
        self.org_id = org_id
        self.base_url = base_url

    @classmethod
    def from_env(cls) -> "DevinClient":
        return cls(
            api_key=os.environ["DEVIN_API_KEY"],
            org_id=os.environ["DEVIN_ORG_ID"],
        )

    def create_session(self, *, prompt: str, tags: list[str] | None = None) -> Session:
        body: dict[str, Any] = {"prompt": prompt}
        if tags:
            body["tags"] = tags
        resp = requests.post(
            self._sessions_url(),
            json=body,
            headers=self._headers(),
            timeout=60,
        )
        resp.raise_for_status()
        return _to_session(resp.json())

    def send_message(self, session_id: str, message: str) -> None:
        resp = requests.post(
            f"{self._sessions_url(session_id)}/messages",
            json={"message": message},
            headers=self._headers(),
            timeout=60,
        )
        resp.raise_for_status()

    def get_session(self, session_id: str) -> Session:
        """Fetch session state, retrying transient 5xx errors with backoff."""
        for attempt in range(5):
            resp = requests.get(
                self._sessions_url(session_id),
                headers=self._headers(),
                timeout=60,
            )
            if resp.ok:
                return _to_session(resp.json())
            if resp.status_code < 500 or attempt == 4:
                resp.raise_for_status()
            time.sleep(2 ** attempt)
        raise RuntimeError("unreachable")

    def wait_for_completion(
        self,
        session_id: str,
        *,
        timeout_seconds: int = 1800,
        poll_interval_seconds: int = 30,
    ) -> Session:
        """Poll until the session reaches a terminal state or produces a PR."""
        deadline = time.monotonic() + timeout_seconds
        while True:
            session = self.get_session(session_id)
            if session.pull_requests or session.status in _TERMINAL_STATUSES:
                return session
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"session {session_id} did not reach a terminal state within "
                    f"{timeout_seconds}s (last status: {session.status}/{session.status_detail})"
                )
            time.sleep(poll_interval_seconds)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _sessions_url(self, session_id: str | None = None) -> str:
        base = f"{self.base_url}/organizations/{self.org_id}/sessions"
        return f"{base}/{_to_devin_id(session_id)}" if session_id else base


def _to_session(payload: dict) -> Session:
    return Session(
        session_id=payload["session_id"],
        url=payload.get("url") or "",
        status=payload.get("status") or "unknown",
        status_detail=payload.get("status_detail"),
        acus_consumed=float(payload.get("acus_consumed") or 0.0),
        pull_requests=list(payload.get("pull_requests") or []),
        structured_output=payload.get("structured_output"),
        tags=list(payload.get("tags") or []),
        raw=payload,
    )


def _to_devin_id(session_id: str) -> str:
    return session_id if session_id.startswith("devin-") else f"devin-{session_id}"
