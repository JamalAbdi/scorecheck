from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import logging
import os
import time
from typing import Any, Dict, List, Optional

import requests

from sports_data.api_sports import ApiSportsConnector, ApiSportsError
from sports_data.thesportsdb import TheSportsDBConnector, TheSportsDBError

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

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
SPORTS_DATA_SOURCE = os.environ.get("SPORTS_DATA_SOURCE", "thesportsdb").lower()

if not APISPORTS_KEY:
    logger.warning("APISPORTS_KEY not set. Using fallback static data.")
else:
    logger.info("APISPORTS_KEY is configured.")

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

LEAGUE_CONFIG: Dict[str, Dict[str, Optional[str]]] = {
    "nba": {
        "name": "NBA",
        "thesportsdb": None,
    },
    "nhl": {
        "name": "NHL",
        "thesportsdb": "NHL",
    },
    "mlb": {
        "name": "MLB",
        "thesportsdb": "MLB",
    },
}

TEAM_CACHE: Dict[str, Dict[str, Any]] = {}
CACHE_TTL_SECONDS = 60
LEAGUE_TEAMS_CACHE: Dict[str, Dict[str, Any]] = {}
LEAGUE_TEAMS_TTL_SECONDS = 3600


def _get_season(team_key: str) -> str:
    env_key = TEAM_CONFIG[team_key]["season_env"]
    return os.environ.get(env_key, DEFAULT_SEASON)


def _connector_for(team_key: str):
    if SPORTS_DATA_SOURCE == "fallback":
        return None  # Use fallback data
    elif SPORTS_DATA_SOURCE == "thesportsdb":
        # TheSportsDB supports NHL, MLB, Soccer but NOT NBA
        if TEAM_CONFIG[team_key]["league"] == "NBA":
            # NBA teams must use API-Sports
            if not APISPORTS_KEY:
                raise ApiSportsError(f"API-Sports key required for NBA teams. TheSportsDB does not support NBA.")
            return ApiSportsConnector(
                APISPORTS_KEY,
                base_url=TEAM_CONFIG[team_key]["base_url"],
            )
        return TheSportsDBConnector()
    else:
        return ApiSportsConnector(
            APISPORTS_KEY,
            base_url=TEAM_CONFIG[team_key]["base_url"],
        )


def _slugify(value: str) -> str:
    import re
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug


def _merge_players(base_players: List[Dict[str, Any]], extra_players: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    merged: Dict[str, Dict[str, Any]] = {player["name"]: player for player in base_players if player.get("name")}
    for player in extra_players:
        name = player.get("name")
        if not name or name in merged:
            continue
        merged[name] = player
    return list(merged.values())


def _fetch_nhl_roster(team_name: str) -> List[Dict[str, Any]]:
    try:
        team_resp = requests.get(
            "https://statsapi.web.nhl.com/api/v1/teams",
            params={"name": team_name},
            timeout=10,
        )
        team_resp.raise_for_status()
        teams = (team_resp.json() or {}).get("teams") or []
        if not teams:
            return []
        team_id = teams[0].get("id")
        if not team_id:
            return []

        roster_resp = requests.get(
            f"https://statsapi.web.nhl.com/api/v1/teams/{team_id}/roster",
            timeout=10,
        )
        roster_resp.raise_for_status()
        roster = (roster_resp.json() or {}).get("roster") or []
        players: List[Dict[str, Any]] = []
        for item in roster:
            person = item.get("person") or {}
            position = item.get("position") or {}
            name = person.get("fullName")
            if not name:
                continue
            players.append(
                {
                    "name": name,
                    "position": position.get("abbreviation") or position.get("name") or "-",
                    "stats": {},
                }
            )
        return players
    except Exception:
        return []


def _fetch_mlb_roster(team_name: str, season: str) -> List[Dict[str, Any]]:
    try:
        team_resp = requests.get(
            "https://statsapi.mlb.com/api/v1/teams",
            params={"name": team_name, "sportId": 1},
            timeout=10,
        )
        team_resp.raise_for_status()
        teams = (team_resp.json() or {}).get("teams") or []
        if not teams:
            return []
        team_id = teams[0].get("id")
        if not team_id:
            return []

        roster_resp = requests.get(
            f"https://statsapi.mlb.com/api/v1/teams/{team_id}/roster",
            params={"season": season},
            timeout=10,
        )
        roster_resp.raise_for_status()
        roster = (roster_resp.json() or {}).get("roster") or []
        players: List[Dict[str, Any]] = []
        for item in roster:
            person = item.get("person") or {}
            position = item.get("position") or {}
            name = person.get("fullName")
            if not name:
                continue
            players.append(
                {
                    "name": name,
                    "position": position.get("abbreviation") or position.get("name") or "-",
                    "stats": {},
                }
            )
        return players
    except Exception:
        return []


def _static_league_teams() -> Dict[str, List[Dict[str, Any]]]:
    nhl_teams = [
        "Anaheim Ducks",
        "Arizona Coyotes",
        "Boston Bruins",
        "Buffalo Sabres",
        "Calgary Flames",
        "Carolina Hurricanes",
        "Chicago Blackhawks",
        "Colorado Avalanche",
        "Columbus Blue Jackets",
        "Dallas Stars",
        "Detroit Red Wings",
        "Edmonton Oilers",
        "Florida Panthers",
        "Los Angeles Kings",
        "Minnesota Wild",
        "Montreal Canadiens",
        "Nashville Predators",
        "New Jersey Devils",
        "New York Islanders",
        "New York Rangers",
        "Ottawa Senators",
        "Philadelphia Flyers",
        "Pittsburgh Penguins",
        "San Jose Sharks",
        "Seattle Kraken",
        "St. Louis Blues",
        "Tampa Bay Lightning",
        "Toronto Maple Leafs",
        "Vancouver Canucks",
        "Vegas Golden Knights",
        "Washington Capitals",
        "Winnipeg Jets",
    ]

    mlb_teams = [
        "Arizona Diamondbacks",
        "Atlanta Braves",
        "Baltimore Orioles",
        "Boston Red Sox",
        "Chicago Cubs",
        "Chicago White Sox",
        "Cincinnati Reds",
        "Cleveland Guardians",
        "Colorado Rockies",
        "Detroit Tigers",
        "Houston Astros",
        "Kansas City Royals",
        "Los Angeles Angels",
        "Los Angeles Dodgers",
        "Miami Marlins",
        "Milwaukee Brewers",
        "Minnesota Twins",
        "New York Mets",
        "New York Yankees",
        "Oakland Athletics",
        "Philadelphia Phillies",
        "Pittsburgh Pirates",
        "San Diego Padres",
        "San Francisco Giants",
        "Seattle Mariners",
        "St. Louis Cardinals",
        "Tampa Bay Rays",
        "Texas Rangers",
        "Toronto Blue Jays",
        "Washington Nationals",
    ]

    return {
        "nhl": [{"id": _slugify(name), "name": name, "league": "NHL"} for name in nhl_teams],
        "mlb": [{"id": _slugify(name), "name": name, "league": "MLB"} for name in mlb_teams],
    }


def _fetch_thesportsdb_league_teams(league_name: str) -> List[Dict[str, Any]]:
    connector = TheSportsDBConnector()

    # First try direct league lookup
    data = connector.get_teams_by_league(league_name)
    teams = connector.extract_teams(data)

    # If TheSportsDB returns a small subset, expand using search queries
    if len(teams) < 20:
        expanded: Dict[str, Dict[str, Any]] = {team["id"]: team for team in teams}
        queries = [chr(c) for c in range(ord("a"), ord("z") + 1)]

        import time

        for query in queries:
            try:
                search_data = connector.get_teams(season=DEFAULT_SEASON, search=query)
            except Exception as exc:
                logger.warning(f"League search aborted at '{query}': {exc}")
                break

            for team in connector.extract_teams(search_data):
                if team.get("league") != league_name:
                    continue
                expanded[team["id"]] = team

            time.sleep(0.2)

        teams = list(expanded.values())

    teams.sort(key=lambda t: t["name"])
    return teams


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
    
    # Static fallback data with players and games
    fallback_data = {
        "raptors": {
            "id": team_id,
            "name": "Toronto Raptors",
            "league": "NBA",
            "players": [
                {"name": "Scottie Barnes", "position": "F", "stats": {"points": 19.5, "rebounds": 8.1, "assists": 6.2}},
                {"name": "RJ Barrett", "position": "G", "stats": {"points": 18.1, "rebounds": 5.4, "assists": 3.1}},
                {"name": "Immanuel Quickley", "position": "G", "stats": {"points": 17.2, "rebounds": 4.3, "assists": 5.9}},
            ],
            "games": [
                {"date": "2026-02-10", "opponent": "Boston Celtics", "home": True, "status": "played", "score": "112-105"},
                {"date": "2026-02-13", "opponent": "Miami Heat", "home": False, "status": "played", "score": "98-101"},
                {"date": "2026-02-25", "opponent": "Chicago Bulls", "home": True, "status": "upcoming", "score": None},
            ],
            "source": "static",
        },
        "maple-leafs": {
            "id": team_id,
            "name": "Toronto Maple Leafs",
            "league": "NHL",
            "players": [
                {"name": "Auston Matthews", "position": "C", "stats": {"goals": 42, "assists": 28, "points": 70}},
                {"name": "Mitch Marner", "position": "RW", "stats": {"goals": 18, "assists": 49, "points": 67}},
                {"name": "William Nylander", "position": "RW", "stats": {"goals": 31, "assists": 34, "points": 65}},
            ],
            "games": [
                {"date": "2026-02-12", "opponent": "Montreal Canadiens", "home": True, "status": "played", "score": "4-2"},
                {"date": "2026-02-15", "opponent": "Ottawa Senators", "home": False, "status": "played", "score": "3-5"},
                {"date": "2026-02-23", "opponent": "Boston Bruins", "home": True, "status": "upcoming", "score": None},
            ],
            "source": "static",
        },
        "blue-jays": {
            "id": team_id,
            "name": "Toronto Blue Jays",
            "league": "MLB",
            "players": [
                {"name": "Vladimir Guerrero Jr.", "position": "1B", "stats": {"avg": 0.291, "hr": 32, "rbi": 98}},
                {"name": "Bo Bichette", "position": "SS", "stats": {"avg": 0.285, "hr": 24, "rbi": 86}},
                {"name": "George Springer", "position": "OF", "stats": {"avg": 0.271, "hr": 22, "rbi": 73}},
            ],
            "games": [
                {"date": "2026-02-08", "opponent": "New York Yankees", "home": False, "status": "played", "score": "6-4"},
                {"date": "2026-02-11", "opponent": "Tampa Bay Rays", "home": True, "status": "played", "score": "2-5"},
                {"date": "2026-02-27", "opponent": "Baltimore Orioles", "home": True, "status": "upcoming", "score": None},
            ],
            "source": "static",
        },
    }
    
    return fallback_data.get(team_id, {
        "id": team_id,
        "name": config["name"],
        "league": config["league"],
        "players": [],
        "games": [],
        "source": "static",
    })


@app.get("/api/health")
def health_check() -> dict:
    return {"status": "ok"}


@app.get("/api/leagues")
def get_leagues() -> dict:
    leagues = []
    for league_id, config in LEAGUE_CONFIG.items():
        available = True
        if SPORTS_DATA_SOURCE == "thesportsdb":
            available = bool(config.get("thesportsdb"))
        elif SPORTS_DATA_SOURCE == "api-sports":
            available = bool(APISPORTS_KEY)
        leagues.append(
            {
                "id": league_id,
                "name": config["name"],
                "available": available,
            }
        )
    return {"leagues": leagues}


@app.get("/api/leagues/{league_id}/teams")
def get_league_teams(league_id: str) -> dict:
    league_key = league_id.lower().strip()
    config = LEAGUE_CONFIG.get(league_key)
    if not config:
        raise HTTPException(status_code=404, detail="League not found")

    static_teams = _static_league_teams().get(league_key)
    if static_teams:
        return {
            "league": config["name"],
            "teams": static_teams,
            "source": "static",
        }

    if SPORTS_DATA_SOURCE != "thesportsdb":
        raise HTTPException(status_code=400, detail="League team listing is only supported with TheSportsDB")

    league_name = config.get("thesportsdb")
    if not league_name:
        raise HTTPException(status_code=400, detail=f"League {config['name']} is not available via TheSportsDB")

    cached = LEAGUE_TEAMS_CACHE.get(league_key)
    if cached and time.time() - cached["timestamp"] < LEAGUE_TEAMS_TTL_SECONDS:
        teams = cached["teams"]
    else:
        try:
            teams = _fetch_thesportsdb_league_teams(league_name)
            LEAGUE_TEAMS_CACHE[league_key] = {"timestamp": time.time(), "teams": teams}
        except TheSportsDBError as exc:
            if "429" in str(exc) and cached:
                logger.warning(f"Rate limited while fetching {league_name}; serving cached data.")
                teams = cached["teams"]
            else:
                raise HTTPException(status_code=429, detail="Rate limited by TheSportsDB. Please retry.")
    return {
        "league": config["name"],
        "teams": teams,
        "source": SPORTS_DATA_SOURCE,
    }


@app.get("/api/leagues/{league_id}/teams/{team_id}")
def get_league_team(league_id: str, team_id: str) -> dict:
    league_key = league_id.lower().strip()
    config = LEAGUE_CONFIG.get(league_key)
    if not config:
        raise HTTPException(status_code=404, detail="League not found")

    if SPORTS_DATA_SOURCE != "thesportsdb":
        raise HTTPException(status_code=400, detail="League team details are only supported with TheSportsDB")

    league_name = config.get("thesportsdb")
    if not league_name:
        raise HTTPException(status_code=400, detail=f"League {config['name']} is not available via TheSportsDB")

    connector = TheSportsDBConnector()

    # If the league is hardcoded, map slug back to team name and resolve via search
    static_teams = _static_league_teams().get(league_key)
    if static_teams:
        matched = next((team for team in static_teams if team["id"] == team_id), None)
        if not matched:
            raise HTTPException(status_code=404, detail="Team not found")
        team_name = matched["name"]
        team_search = connector.get_teams(season=DEFAULT_SEASON, search=team_name)
        team_info = connector.extract_team(team_search)
        external_id = (team_info or {}).get("id")
        if not external_id:
            raise HTTPException(status_code=404, detail="Team not found in TheSportsDB")
    else:
        team_info = connector.extract_team(connector.get_team_by_id(team_id))
        team_name = (team_info or {}).get("name", "Unknown")
        external_id = team_id

    players_response = connector.get_players(season=DEFAULT_SEASON, team_id=external_id)
    games_response = connector.get_games(season=DEFAULT_SEASON, team_id=external_id)

    players = connector.extract_players(players_response)
    if config["name"] == "NHL" and len(players) < 15:
        players = _merge_players(players, _fetch_nhl_roster(team_name))
    if config["name"] == "MLB" and len(players) < 15:
        players = _merge_players(players, _fetch_mlb_roster(team_name, DEFAULT_SEASON))

    return {
        "id": team_id,
        "name": team_name,
        "league": config["name"],
        "players": players,
        "games": connector.extract_games(games_response, team_name),
        "source": SPORTS_DATA_SOURCE,
    }


@app.get("/api/teams")
def get_teams() -> dict:
    teams = []
    for team_id, config in TEAM_CONFIG.items():
        entry = {"id": team_id, "name": config["name"], "league": config["league"]}
        if SPORTS_DATA_SOURCE != "fallback":
            try:
                connector = _connector_for(team_id)
                season = _get_season(team_id)
                data = connector.get_teams(season=season, search=config["search"])
                team_info = connector.extract_team(data)
                if team_info and team_info.get("id"):
                    entry["external_id"] = team_info.get("id")
                    entry["name"] = team_info.get("name", entry["name"])
            except Exception:
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
    logger.debug(f"GET /api/teams/{team_id}")
    if team_id not in TEAM_CONFIG:
        logger.warning(f"Team not found: {team_id}")
        raise HTTPException(status_code=404, detail="Team not found")

    cached = TEAM_CACHE.get(team_id)
    if cached and time.time() - cached["timestamp"] < CACHE_TTL_SECONDS:
        logger.debug(f"Returning cached data for {team_id}")
        return cached["data"]

    if SPORTS_DATA_SOURCE == "fallback":
        logger.debug(f"Using fallback data for {team_id}")
        result = _fallback_team(team_id)
        TEAM_CACHE[team_id] = {"timestamp": time.time(), "data": result}
        return result

    try:
        config = TEAM_CONFIG[team_id]
        connector = _connector_for(team_id)
        season = _get_season(team_id)
        logger.debug(f"Fetching {team_id} from {SPORTS_DATA_SOURCE} with season {season}")

        teams_response = connector.get_teams(season=season, search=config["search"])
        logger.debug(f"Teams response for {team_id}: {teams_response}")
        team_info = connector.extract_team(teams_response)
        logger.debug(f"Extracted team info: {team_info}")
        team_name = (team_info or {}).get("name", config["name"])
        external_id = (team_info or {}).get("id")
        logger.debug(f"Team info: name={team_name}, id={external_id}")

        players_response = connector.get_players(
            season=season,
            team_id=external_id,
            search=config["search"] if external_id is None else None,
        )
        logger.debug(f"Players response: {players_response}")
        games_response = connector.get_games(
            season=season,
            team_id=external_id,
            search=config["search"] if external_id is None else None,
        )
        logger.debug(f"Games response: {games_response}")

        team_data = {
            "id": team_id,
            "name": team_name,
            "league": config["league"],
            "players": connector.extract_players(players_response),
            "games": connector.extract_games(games_response, team_name),
            "source": SPORTS_DATA_SOURCE,
        }
        logger.debug(f"Successfully fetched {team_id} from {SPORTS_DATA_SOURCE}")
    except Exception as exc:
        logger.error(f"Error fetching {team_id} from {SPORTS_DATA_SOURCE}: {exc}")
        team_data = _fallback_team(team_id)
        team_data["warning"] = str(exc)

    TEAM_CACHE[team_id] = {"timestamp": time.time(), "data": team_data}
    return team_data
