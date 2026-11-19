"""Shared HTTP client with retries for upstream APIs."""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

_local = threading.local()
RETRY_STATUS = {429, 500, 502, 503, 504}


class UpstreamError(Exception):
    """A third-party service failed or returned something unusable."""


class ValidationError(Exception):
    """The client sent an invalid request."""


def _session() -> requests.Session:
    session = getattr(_local, "session", None)
    if session is None:
        session = requests.Session()
        session.headers["User-Agent"] = settings.HTTP_USER_AGENT
        _local.session = session
    return session


def get_json(url: str, params: dict[str, Any] | None = None, *, service: str, timeout: float = 20, attempts: int = 3) -> Any:
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            resp = _session().get(url, params=params, timeout=timeout)
            if resp.status_code in RETRY_STATUS and attempt < attempts - 1:
                time.sleep(0.75 * (2**attempt))
                continue
            if resp.status_code >= 400:
                detail = resp.text[:200]
                try:
                    body = resp.json()
                    detail = body.get("reason") or body.get("message") or detail
                except ValueError:
                    pass
                raise UpstreamError(f"{service} returned HTTP {resp.status_code}: {detail}")
            return resp.json()
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            logger.warning("%s request failed (attempt %d): %s", service, attempt + 1, exc)
            if attempt < attempts - 1:
                time.sleep(0.75 * (2**attempt))
    raise UpstreamError(f"{service} is unavailable: {last_error}")
