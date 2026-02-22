from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import os
import time
from typing import Any, Dict, List, Optional

from api_sports import ApiSportsBaseConnector, ApiSportsError

app = FastAPI(title="Scorecheck API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

APISPORTS_KEY = os.environ.get("APISPORTS_KEY", "").strip()
DEFAULT_SEASON = os.environ.get("APISPORTS_SEASON", "2024").strip()

TEAM_CONFIG: Dict[str, Dict[str, str]] = {
    "raptors": {
        "name": "Toronto Raptors",
        "league": "NBA",
        "base_url": "https://v2.nba.api-sports.io",
        "search": "Raptors",
        "season_env": "APISPORTS_NBA_SEASON",
    },
    "maple-leafs": {
        "name": "Toronto Maple Leafs",
        "league": "NHL",
        "base_url": "https://v1.hockey.api-sports.io",
        "search": "Maple Leafs",
        "season_env": "APISPORTS_NHL_SEASON",
    },
    "blue-jays": {
        "name": "Toronto Blue Jays",
        "league": "MLB",
        "base_url": "https://v1.baseball.api-sports.io",
        "search": "Blue Jays",
        "season_env": "APISPORTS_MLB_SEASON",
    },
}

TEAM_CACHE: Dict[str, Dict[str, Any]] = {}
CACHE_TTL_SECONDS = 60


def _get_season(team_key: str) -> str:
    env_key = TEAM_CONFIG[team_key]["season_env"]
    return os.environ.get(env_key, DEFAULT_SEASON)


def _connector_for(team_key: str) -> ApiSportsBaseConnector:
    return ApiSportsBaseConnector(
        APISPORTS_KEY,
        base_url=TEAM_CONFIG[team_key]["base_url"],
    )


def _extract_team(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    response = data.get("response") or []
    for item in response:
        if isinstance(item, dict):
            if isinstance(item.get("team"), dict):
                return item.get("team")
            if "name" in item:
                return item
    return None


def _flatten_stats(stats: Dict[str, Any]) -> Dict[str, Any]:
    flattened: Dict[str, Any] = {}
    for key, value in stats.items():
        if isinstance(value, (int, float)):
            flattened[key] = value
    return flattened


def _extract_players(data: Dict[str, Any]) -> List[Dict[str, Any]]:
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

        stats = _flatten_stats(stats_source)

        players.append(
            {
                "name": name or "Unknown",
                "position": position,
                "stats": stats,
            }
        )

    return players


def _score_value(value: Any) -> Optional[float]:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, dict):
        for key in ("total", "points", "goals", "runs", "score"):
            if isinstance(value.get(key), (int, float)):
                return float(value.get(key))
    return None


def _extract_score(item: Dict[str, Any]) -> Optional[str]:
    scores = item.get("scores") or item.get("score")
    if isinstance(scores, dict):
        home_score = _score_value(scores.get("home"))
        away_score = _score_value(scores.get("away"))
        if home_score is not None and away_score is not None:
            return f"{int(home_score)}-{int(away_score)}"
    if isinstance(scores, (int, float)):
        return str(scores)
    return None


def _extract_games(data: Dict[str, Any], team_name: str) -> List[Dict[str, Any]]:
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

        score = _extract_score(item)
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


def _fallback_team(team_id: str) -> Dict[str, Any]:
    config = TEAM_CONFIG[team_id]
    return {
        "id": team_id,
        "name": config["name"],
        "league": config["league"],
        "players": [],
        "games": [],
        "source": "static",
    }


@app.get("/api/health")
def health_check() -> dict:
    return {"status": "ok"}


@app.get("/api/teams")
def get_teams() -> dict:
    teams = []
    for team_id, config in TEAM_CONFIG.items():
        entry = {"id": team_id, "name": config["name"], "league": config["league"]}
        if APISPORTS_KEY:
            try:
                connector = _connector_for(team_id)
                season = _get_season(team_id)
                data = connector.get("/teams", params={"search": config["search"], "season": season})
                team_info = _extract_team(data)
                if team_info and team_info.get("id"):
                    entry["external_id"] = team_info.get("id")
                    entry["name"] = team_info.get("name", entry["name"])
            except ApiSportsError:
                entry["source"] = "static"
        teams.append(entry)
    return {"teams": teams}


TEAM_DETAILS = {
    "raptors": {
        "id": "raptors",
        "name": "Toronto Raptors",
        "league": "NBA",
        "players": [
            {"name": "Scottie Barnes", "position": "F", "points": 19.5, "rebounds": 8.1, "assists": 6.2},
            {"name": "RJ Barrett", "position": "G", "points": 18.1, "rebounds": 5.4, "assists": 3.1},
            {"name": "Immanuel Quickley", "position": "G", "points": 17.2, "rebounds": 4.3, "assists": 5.9},
        ],
        "games": [
            {"date": "2026-02-10", "opponent": "Boston Celtics", "home": True, "status": "played", "score": "112-105"},
            {"date": "2026-02-13", "opponent": "Miami Heat", "home": False, "status": "played", "score": "98-101"},
            {"date": "2026-02-25", "opponent": "Chicago Bulls", "home": True, "status": "upcoming", "score": None},
        ],
    },
    "maple-leafs": {
        "id": "maple-leafs",
        "name": "Toronto Maple Leafs",
        "league": "NHL",
        "players": [
            {"name": "Auston Matthews", "position": "C", "goals": 42, "assists": 28, "points": 70},
            {"name": "Mitch Marner", "position": "RW", "goals": 18, "assists": 49, "points": 67},
            {"name": "William Nylander", "position": "RW", "goals": 31, "assists": 34, "points": 65},
        ],
        "games": [
            {"date": "2026-02-12", "opponent": "Montreal Canadiens", "home": True, "status": "played", "score": "4-2"},
            {"date": "2026-02-15", "opponent": "Ottawa Senators", "home": False, "status": "played", "score": "3-5"},
            {"date": "2026-02-23", "opponent": "Boston Bruins", "home": True, "status": "upcoming", "score": None},
        ],
    },
    "blue-jays": {
        "id": "blue-jays",
        "name": "Toronto Blue Jays",
        "league": "MLB",
        "players": [
            {"name": "Vladimir Guerrero Jr.", "position": "1B", "avg": 0.291, "hr": 32, "rbi": 98},
            {"name": "Bo Bichette", "position": "SS", "avg": 0.285, "hr": 24, "rbi": 86},
            {"name": "George Springer", "position": "OF", "avg": 0.271, "hr": 22, "rbi": 73},
        ],
        "games": [
            {"date": "2026-02-08", "opponent": "New York Yankees", "home": False, "status": "played", "score": "6-4"},
            {"date": "2026-02-11", "opponent": "Tampa Bay Rays", "home": True, "status": "played", "score": "2-5"},
            {"date": "2026-02-27", "opponent": "Baltimore Orioles", "home": True, "status": "upcoming", "score": None},
        ],
    },
}


@app.get("/api/teams/{team_id}")
def get_team(team_id: str) -> dict:
    if team_id not in TEAM_CONFIG:
        raise HTTPException(status_code=404, detail="Team not found")

    cached = TEAM_CACHE.get(team_id)
    if cached and time.time() - cached["timestamp"] < CACHE_TTL_SECONDS:
        return cached["data"]

    if not APISPORTS_KEY:
        return _fallback_team(team_id)

    try:
        config = TEAM_CONFIG[team_id]
        connector = _connector_for(team_id)
        season = _get_season(team_id)

        teams_response = connector.get("/teams", params={"search": config["search"], "season": season})
        team_info = _extract_team(teams_response)
        team_name = (team_info or {}).get("name", config["name"])
        external_id = (team_info or {}).get("id")

        players_response = connector.get(
            "/players",
            params={"search": config["search"], "season": season} if external_id is None else {"team": external_id, "season": season},
        )
        games_response = connector.get(
            "/games",
            params={"team": external_id, "season": season} if external_id is not None else {"season": season, "search": config["search"]},
        )

        team_data = {
            "id": team_id,
            "name": team_name,
            "league": config["league"],
            "players": _extract_players(players_response),
            "games": _extract_games(games_response, team_name),
            "source": "api-sports",
        }
    except ApiSportsError as exc:
        team_data = _fallback_team(team_id)
        team_data["warning"] = str(exc)

    TEAM_CACHE[team_id] = {"timestamp": time.time(), "data": team_data}
    return team_data
