from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

import requests

from .base import BaseSportDataConnector, SportsDataError

Json = Dict[str, Any]


class ESPNError(SportsDataError):
    """ESPN connector errors."""


class ESPNConnector(BaseSportDataConnector):
    """Connector for ESPN public JSON endpoints."""

    BASE_URL = "https://site.api.espn.com/apis/site/v2"

    LEAGUE_PATHS = {
        "NBA": {
            "sport": "basketball",
            "league": "nba",
        },
        "NHL": {
            "sport": "hockey",
            "league": "nhl",
        },
        "MLB": {
            "sport": "baseball",
            "league": "mlb",
        },
    }

    def __init__(
        self,
        *,
        league_name: str,
        timeout_seconds: float = 20.0,
        session: Optional[requests.Session] = None,
        user_agent: str = "scorecheck-api/1.0",
    ) -> None:
        path_info = self.LEAGUE_PATHS.get(league_name)
        if not path_info:
            raise ESPNError(f"Unsupported league for ESPN connector: {league_name}")

        self._path_info = path_info
        self._base_url = self.BASE_URL
        self._timeout = timeout_seconds
        self._session = session or requests.Session()
        self._user_agent = user_agent

    def _headers(self) -> Dict[str, str]:
        return {
            "Accept": "application/json",
            "User-Agent": self._user_agent,
        }

    def _get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Json:
        try:
            url = f"{self._base_url}{endpoint}"
            resp = self._session.get(
                url,
                headers=self._headers(),
                params=dict(params or {}),
                timeout=self._timeout,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            raise ESPNError(f"Request failed: {exc}") from exc
        except ValueError as exc:
            raise ESPNError(f"Invalid JSON response: {exc}") from exc

    def _teams_endpoint(self) -> str:
        sport = self._path_info["sport"]
        league = self._path_info["league"]
        return f"/sports/{sport}/{league}/teams"

    def _team_endpoint(self, team_id: str, suffix: str) -> str:
        sport = self._path_info["sport"]
        league = self._path_info["league"]
        return f"/sports/{sport}/{league}/teams/{team_id}/{suffix}"

    def _scoreboard_endpoint(self) -> str:
        sport = self._path_info["sport"]
        league = self._path_info["league"]
        return f"/sports/{sport}/{league}/scoreboard"

    def _all_teams(self) -> List[Dict[str, Any]]:
        data = self._get(self._teams_endpoint(), params={"limit": 200})
        sports = data.get("sports") if isinstance(data, dict) else None
        if not isinstance(sports, list) or not sports:
            return []

        leagues = (sports[0] or {}).get("leagues")
        teams = ((leagues or [{}])[0] or {}).get("teams")
        if not isinstance(teams, list):
            return []

        result: List[Dict[str, Any]] = []
        for entry in teams:
            team = entry.get("team") if isinstance(entry, dict) else None
            if isinstance(team, dict):
                result.append(team)
        return result

    def _resolve_team_id(
        self,
        season: str,
        team_id: Optional[int] = None,
        search: Optional[str] = None,
    ) -> Optional[str]:
        if team_id is not None:
            return str(team_id)

        teams = self.get_teams(season=season, search=search)
        team_info = self.extract_team(teams)
        if not isinstance(team_info, dict):
            return None
        resolved = team_info.get("id")
        return str(resolved) if resolved is not None else None

    def get_teams(self, season: str, search: Optional[str] = None) -> Json:
        teams = self._all_teams()
        if search:
            needle = search.lower().strip()
            filtered = []
            for team in teams:
                values = [
                    str(team.get("displayName") or ""),
                    str(team.get("name") or ""),
                    str(team.get("shortDisplayName") or ""),
                    str(team.get("location") or ""),
                    str(team.get("slug") or ""),
                ]
                if any(needle in value.lower() for value in values):
                    filtered.append(team)
            teams = filtered

        return {"response": [{"team": team} for team in teams]}

    def get_players(
        self, season: str, team_id: Optional[int] = None, search: Optional[str] = None
    ) -> Json:
        resolved_team_id = self._resolve_team_id(season, team_id=team_id, search=search)
        if not resolved_team_id:
            return {"athletes": []}

        data = self._get(self._team_endpoint(resolved_team_id, "roster"))
        athletes = data.get("athletes") if isinstance(data, dict) else None

        return {"athletes": athletes or []}

    def get_games(
        self,
        season: str,
        team_id: Optional[int] = None,
        date: Optional[str] = None,
        search: Optional[str] = None,
    ) -> Json:
        resolved_team_id = self._resolve_team_id(season, team_id=team_id, search=search)
        if not resolved_team_id:
            return {"events": []}

        params: Dict[str, Any] = {}
        if season:
            try:
                season_str = str(season).strip()
                if "-" in season_str:
                    season_parts = [
                        part.strip()
                        for part in season_str.split("-")
                        if part.strip()
                    ]
                    params["season"] = int(season_parts[-1])
                else:
                    params["season"] = int(season_str)
            except ValueError:
                params["season"] = season
        if date:
            params["dates"] = date

        data = self._get(
            self._team_endpoint(resolved_team_id, "schedule"), params=params
        )

        events = data.get("events") if isinstance(data, dict) else None
        if search and isinstance(events, list):
            needle = search.lower().strip()
            events = [
                event
                for event in events
                if isinstance(event, dict)
                and needle
                in str(event.get("name") or event.get("shortName") or "").lower()
            ]

        return {"events": events or []}

    def get_scoreboard(self, date: Optional[str] = None) -> Json:
        params: Dict[str, Any] = {}
        if date:
            params["dates"] = date
        data = self._get(self._scoreboard_endpoint(), params=params)
        events = data.get("events") if isinstance(data, dict) else None
        return {"events": events or []}

    def extract_team(self, data: Json) -> Optional[Dict[str, Any]]:
        response = data.get("response") if isinstance(data, dict) else None
        if isinstance(response, list) and response:
            first = response[0] or {}
            team = first.get("team") if isinstance(first, dict) else None
            if not isinstance(team, dict) and isinstance(first, dict):
                team = first
            if isinstance(team, dict):
                logo = ""
                logos = team.get("logos")
                if isinstance(logos, list):
                    for logo_item in logos:
                        if not isinstance(logo_item, dict):
                            continue
                        href = str(logo_item.get("href") or "").strip()
                        if href:
                            logo = href
                            break
                if not logo:
                    abbreviation = str(team.get("abbreviation") or "").strip().lower()
                    if abbreviation:
                        league_code = self._path_info.get("league", "")
                        logo = (
                            f"https://a.espncdn.com/i/teamlogos/{league_code}/500/"
                            f"scoreboard/{abbreviation}.png"
                        )
                return {
                    "id": team.get("id"),
                    "name": team.get("displayName") or team.get("name"),
                    "logo": logo,
                }
        return None

    def extract_players(self, data: Json) -> List[Dict[str, Any]]:
        athletes = data.get("athletes") if isinstance(data, dict) else None
        if not isinstance(athletes, list):
            return []

        flattened_athletes: List[Dict[str, Any]] = []
        for entry in athletes:
            if not isinstance(entry, dict):
                continue
            if isinstance(entry.get("items"), list):
                group_position = str(entry.get("position") or "").strip()
                for grouped_athlete in entry.get("items") or []:
                    if not isinstance(grouped_athlete, dict):
                        continue
                    if group_position and not isinstance(
                        grouped_athlete.get("position"), dict
                    ):
                        grouped_athlete = dict(grouped_athlete)
                        grouped_athlete["position"] = {"abbreviation": group_position}
                    flattened_athletes.append(grouped_athlete)
            else:
                flattened_athletes.append(entry)

        players: List[Dict[str, Any]] = []
        for athlete in flattened_athletes:
            if not isinstance(athlete, dict):
                continue
            name = athlete.get("fullName") or athlete.get("displayName")
            if not name:
                continue
            position = (athlete.get("position") or {}).get("abbreviation") or "-"
            players.append(
                {
                    "name": name,
                    "position": position,
                    "stats": {},
                }
            )

        return players

    def extract_games(self, data: Json, team_name: str) -> List[Dict[str, Any]]:
        events = data.get("events") if isinstance(data, dict) else None
        if not isinstance(events, list):
            return []

        team_name_lower = team_name.lower()
        games: List[Dict[str, Any]] = []

        def _parse_score(raw_score: Any) -> Optional[int]:
            if isinstance(raw_score, int):
                return raw_score
            if isinstance(raw_score, float):
                return int(raw_score)
            if isinstance(raw_score, str):
                cleaned = raw_score.strip()
                if cleaned == "":
                    return None
                try:
                    return int(cleaned)
                except ValueError:
                    return None
            if isinstance(raw_score, dict):
                for key in ("value", "displayValue"):
                    value = raw_score.get(key)
                    parsed = _parse_score(value)
                    if parsed is not None:
                        return parsed
            return None

        for event in events:
            if not isinstance(event, dict):
                continue

            competition = None
            competitions = event.get("competitions")
            if (
                isinstance(competitions, list)
                and competitions
                and isinstance(competitions[0], dict)
            ):
                competition = competitions[0]

            competitors = (
                competition.get("competitors")
                if isinstance(competition, dict)
                else None
            )
            if not isinstance(competitors, list):
                continue

            home_team_name = None
            away_team_name = None
            home_score = None
            away_score = None

            for competitor in competitors:
                if not isinstance(competitor, dict):
                    continue
                team = competitor.get("team") or {}
                display_name = str(team.get("displayName") or "")
                is_home = competitor.get("homeAway") == "home"
                score_val = competitor.get("score")
                parsed_score = _parse_score(score_val)

                if is_home:
                    home_team_name = display_name
                    home_score = parsed_score
                else:
                    away_team_name = display_name
                    away_score = parsed_score

            if not home_team_name or not away_team_name:
                continue

            is_home_game = team_name_lower == home_team_name.lower()
            is_away_game = team_name_lower == away_team_name.lower()
            if not is_home_game and not is_away_game:
                continue

            opponent = away_team_name if is_home_game else home_team_name

            score = None
            status = "upcoming"
            if home_score is not None and away_score is not None:
                score = f"{home_score}-{away_score}"
                status = "played"

            event_date = str(event.get("date") or "")
            game_date = ""
            if event_date:
                try:
                    game_date = (
                        datetime.fromisoformat(event_date.replace("Z", "+00:00"))
                        .date()
                        .isoformat()
                    )
                except ValueError:
                    game_date = event_date[:10]

            games.append(
                {
                    "id": event.get("id") or "",
                    "date": game_date,
                    "opponent": opponent,
                    "home": is_home_game,
                    "status": status,
                    "score": score,
                }
            )

        played_games = [game for game in games if game.get("status") == "played"]
        played_games.sort(key=lambda game: game.get("date") or "", reverse=True)
        return played_games

    def extract_scoreboard_games(self, data: Json) -> List[Dict[str, Any]]:
        events = data.get("events") if isinstance(data, dict) else None
        if not isinstance(events, list):
            return []

        games: List[Dict[str, Any]] = []

        def _record_summary(competitor: Dict[str, Any]) -> str:
            records = competitor.get("records")
            if isinstance(records, list):
                for record in records:
                    if not isinstance(record, dict):
                        continue
                    summary = str(record.get("summary") or "").strip()
                    if summary:
                        return summary
            return "-"

        def _score_value(competitor: Dict[str, Any]) -> str:
            raw = competitor.get("score")
            return str(raw) if raw not in (None, "") else "-"

        def _logo_url(team: Dict[str, Any]) -> str:
            logos = team.get("logos")
            if isinstance(logos, list):
                for logo in logos:
                    if not isinstance(logo, dict):
                        continue
                    href = str(logo.get("href") or "").strip()
                    if href:
                        return href

            direct_logo = str(team.get("logo") or "").strip()
            if direct_logo:
                return direct_logo

            abbreviation = str(team.get("abbreviation") or "").strip().lower()
            if abbreviation:
                league_code = self._path_info.get("league", "")
                return (
                    f"https://a.espncdn.com/i/teamlogos/{league_code}/500/"
                    f"{abbreviation}.png"
                )
            return ""

        for event in events:
            if not isinstance(event, dict):
                continue

            competition = None
            competitions = event.get("competitions")
            if (
                isinstance(competitions, list)
                and competitions
                and isinstance(competitions[0], dict)
            ):
                competition = competitions[0]

            competitors = (
                competition.get("competitors")
                if isinstance(competition, dict)
                else None
            )
            if not isinstance(competitors, list):
                continue

            home_competitor = None
            away_competitor = None
            for competitor in competitors:
                if not isinstance(competitor, dict):
                    continue
                if competitor.get("homeAway") == "home":
                    home_competitor = competitor
                elif competitor.get("homeAway") == "away":
                    away_competitor = competitor

            if not isinstance(home_competitor, dict) or not isinstance(
                away_competitor, dict
            ):
                continue

            home_team = home_competitor.get("team") or {}
            away_team = away_competitor.get("team") or {}

            event_date = str(event.get("date") or "")
            game_date = ""
            if event_date:
                try:
                    game_date = (
                        datetime.fromisoformat(event_date.replace("Z", "+00:00"))
                        .date()
                        .isoformat()
                    )
                except ValueError:
                    game_date = event_date[:10]

            games.append(
                {
                    "id": event.get("id") or "",
                    "date": game_date,
                    "start_time": event_date,
                    "status": ((event.get("status") or {}).get("type") or {}).get(
                        "detail"
                    )
                    or ((event.get("status") or {}).get("type") or {}).get(
                        "shortDetail"
                    )
                    or ((event.get("status") or {}).get("type") or {}).get(
                        "description"
                    )
                    or "",
                    "home_team": home_team.get("displayName")
                    or home_team.get("name")
                    or "",
                    "away_team": away_team.get("displayName")
                    or away_team.get("name")
                    or "",
                    "home_logo": _logo_url(home_team),
                    "away_logo": _logo_url(away_team),
                    "home_score": _score_value(home_competitor),
                    "away_score": _score_value(away_competitor),
                    "home_record": _record_summary(home_competitor),
                    "away_record": _record_summary(away_competitor),
                }
            )

        return games
