from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, TypeVar
import time

import requests
from requests import Response

Json = Dict[str, Any]
T = TypeVar("T")


class ApiSportsError(Exception):
    """Base exception for API-Sports connector errors."""


class ApiSportsAuthError(ApiSportsError):
    """401/403 errors."""


class ApiSportsRateLimitError(ApiSportsError):
    """429 errors."""


class ApiSportsHttpError(ApiSportsError):
    """Non-success HTTP errors that aren't auth/rate-limit."""


class ApiSportsResponseError(ApiSportsError):
    """Response JSON is missing expected structure / indicates API error."""


@dataclass(frozen=True)
class RetryConfig:
    max_retries: int = 3
    backoff_seconds: float = 0.6
    backoff_multiplier: float = 2.0
    retry_statuses: tuple[int, ...] = (429, 500, 502, 503, 504)


class ApiSportsBaseConnector:
    """
    Base connector for API-Sports style APIs.

    Notes:
    - API key is sent via `x-apisports-key` header.
    - `get()` accepts an endpoint like "/teams" or "teams".
    """

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str,
        timeout_seconds: float = 20.0,
        retry: RetryConfig = RetryConfig(),
        session: Optional[requests.Session] = None,
        user_agent: str = "scorecheck-api/1.0",
    ) -> None:
        if not api_key or not api_key.strip():
            raise ValueError("api_key must be a non-empty string")

        base_url = base_url.strip().rstrip("/")
        if not base_url:
            raise ValueError("base_url is required")

        self._api_key = api_key.strip()
        self._base_url = base_url
        self._timeout = timeout_seconds
        self._retry = retry
        self._session = session or requests.Session()
        self._user_agent = user_agent

    def _headers(self) -> Dict[str, str]:
        return {
            "x-apisports-key": self._api_key,
            "Accept": "application/json",
            "User-Agent": self._user_agent,
        }

    def _make_url(self, endpoint: str) -> str:
        endpoint = endpoint.strip()
        if not endpoint:
            raise ValueError("endpoint must be non-empty")
        if not endpoint.startswith("/"):
            endpoint = "/" + endpoint
        return f"{self._base_url}{endpoint}"

    def _handle_http_errors(self, resp: Response) -> None:
        if resp.status_code in (401, 403):
            raise ApiSportsAuthError(f"Auth error ({resp.status_code}). Check API key / plan / whitelist.")
        if resp.status_code == 429:
            raise ApiSportsRateLimitError("Rate limited (429).")
        if 400 <= resp.status_code:
            raise ApiSportsHttpError(f"HTTP error {resp.status_code}: {resp.text[:500]}")

    def _parse_json(self, resp: Response) -> Json:
        try:
            data: Json = resp.json()
        except Exception as exc:  # pragma: no cover - best effort parsing
            raise ApiSportsResponseError(f"Failed to decode JSON: {exc}") from exc

        errors = data.get("errors")
        if isinstance(errors, dict) and errors:
            raise ApiSportsResponseError(f"API returned errors: {errors}")
        if isinstance(errors, list) and len(errors) > 0:
            raise ApiSportsResponseError(f"API returned errors: {errors}")

        return data

    def get(self, endpoint: str, params: Optional[Mapping[str, Any]] = None) -> Json:
        url = self._make_url(endpoint)
        params_dict = dict(params or {})

        last_err: Optional[Exception] = None
        delay = self._retry.backoff_seconds

        for attempt in range(self._retry.max_retries + 1):
            try:
                resp = self._session.get(
                    url,
                    headers=self._headers(),
                    params=params_dict,
                    timeout=self._timeout,
                )
                if resp.status_code in self._retry.retry_statuses and attempt < self._retry.max_retries:
                    retry_after = resp.headers.get("Retry-After")
                    if retry_after:
                        try:
                            time.sleep(float(retry_after))
                        except ValueError:
                            time.sleep(delay)
                    else:
                        time.sleep(delay)
                    delay *= self._retry.backoff_multiplier
                    continue

                self._handle_http_errors(resp)
                return self._parse_json(resp)

            except (requests.Timeout, requests.ConnectionError) as exc:
                last_err = exc
                if attempt >= self._retry.max_retries:
                    break
                time.sleep(delay)
                delay *= self._retry.backoff_multiplier
            except Exception as exc:  # pragma: no cover - best effort
                last_err = exc
                break

        raise ApiSportsError(f"Request failed after retries. Last error: {last_err}") from last_err
