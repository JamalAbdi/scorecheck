from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, TypeVar
import time

import requests
from requests import Response

from .base import BaseSportDataConnector, SportsDataError

Json = Dict[str, Any]
T = TypeVar("T")


class ApiSportsError(SportsDataError):
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


class ApiSportsConnector(BaseSportDataConnector):
    """
    Connector for API-Sports APIs.

    Notes:
    - API key is sent via `x-apisports-key` header.
    - Supports NBA, NHL, MLB via different base URLs.
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
        except Exception as exc:
            raise ApiSportsResponseError(f"Failed to decode JSON: {exc}") from exc

        errors = data.get("errors")
        if isinstance(errors, dict) and errors:
            raise ApiSportsResponseError(f"API returned errors: {errors}")
        if isinstance(errors, list) and len(errors) > 0:
            raise ApiSportsResponseError(f"API returned errors: {errors}")

        return data

    def _get(self, endpoint: str, params: Optional[Mapping[str, Any]] = None) -> Json:
        """Internal GET with retry logic."""
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
            except Exception as exc:
                last_err = exc
                break

        raise ApiSportsError(f"Request failed after retries. Last error: {last_err}") from last_err

    def get_teams(self, season: str, search: Optional[str] = None) -> Json:
        params: Dict[str, Any] = {"season": season}
        if search:
            params["search"] = search
        return self._get("/teams", params=params)

    def get_players(self, season: str, team_id: Optional[int] = None, search: Optional[str] = None) -> Json:
        params: Dict[str, Any] = {"season": season}
        if team_id:
            params["team"] = team_id
        if search:
            params["search"] = search
        return self._get("/players", params=params)

    def get_games(self, season: str, team_id: Optional[int] = None, date: Optional[str] = None, search: Optional[str] = None) -> Json:
        params: Dict[str, Any] = {"season": season}
        if team_id:
            params["team"] = team_id
        if date:
            params["date"] = date
        if search:
            params["search"] = search
        return self._get("/games", params=params)

    def extract_team(self, data: Json) -> Optional[Dict[str, Any]]:
        response = data.get("response") or []
        for item in response:
            if isinstance(item, dict):
                if isinstance(item.get("team"), dict):
                    return item.get("team")
                if "name" in item:
                    return item
        return None

    def extract_players(self, data: Json) -> List[Dict[str, Any]]:
        response = data.get("response") or []
        players: List[Dict[str, Any]] = []
        for item in response:
            if not isinstance(item, dict):
                continue
            player_info = item.get("player") if isinstance(item.get("player"), dict) else item
            name = player_info.get("name") or " ".join(
                part for part in [player_info.get("firstname"), player_info.get("lastname")] if part
            )
            position = player_info.get("position") or player_info.get("pos") or "-"

            stats_source: Dict[str, Any] = {}
            statistics = item.get("statistics")
            if isinstance(statistics, list) and statistics:
                if isinstance(statistics[0], dict):
                    stats_source = statistics[0]
            elif isinstance(item.get("stats"), dict):
                stats_source = item.get("stats")

            stats = {k: v for k, v in stats_source.items() if isinstance(v, (int, float))}

            players.append(
                {
                    "name": name or "Unknown",
                    "position": position,
                    "stats": stats,
                }
            )

        return players

    def extract_games(self, data: Json, team_name: str) -> List[Dict[str, Any]]:
        response = data.get("response") or []
        games: List[Dict[str, Any]] = []
        for item in response:
            if not isinstance(item, dict):
                continue

            date = item.get("date")
            if not date and isinstance(item.get("game"), dict):
                date = item.get("game", {}).get("date")

            home_name = None
            away_name = None
            teams = item.get("teams")
            if isinstance(teams, dict):
                home_name = (teams.get("home") or {}).get("name")
                away_name = (teams.get("away") or {}).get("name")

            home = None
            opponent = None
            if home_name and away_name:
                if team_name.lower() == home_name.lower():
                    home = True
                    opponent = away_name
                elif team_name.lower() == away_name.lower():
                    home = False
                    opponent = home_name

            def _score_value(value: Any) -> Optional[float]:
                if isinstance(value, (int, float)):
                    return float(value)
                if isinstance(value, dict):
                    for key in ("total", "points", "goals", "runs", "score"):
                        if isinstance(value.get(key), (int, float)):
                            return float(value.get(key))
                return None

            scores = item.get("scores") or item.get("score")
            score = None
            if isinstance(scores, dict):
                home_score = _score_value(scores.get("home"))
                away_score = _score_value(scores.get("away"))
                if home_score is not None and away_score is not None:
                    score = f"{int(home_score)}-{int(away_score)}"
            if isinstance(scores, (int, float)):
                score = str(scores)

            status = "played" if score else "upcoming"

            games.append(
                {
                    "date": date or "",
                    "opponent": opponent or "TBD",
                    "home": bool(home) if home is not None else False,
                    "status": status,
                    "score": score,
                }
            )

        return games[:10]
