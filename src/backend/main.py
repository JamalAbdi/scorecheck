from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import json
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

import requests
from sqlalchemy import create_engine, Column, String, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from sports_data.espn import ESPNConnector
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

DEFAULT_SEASON = os.environ.get("SCORECHECK_SEASON", "2024").strip()
SPORTS_DATA_SOURCE = os.environ.get("SPORTS_DATA_SOURCE", "espn").lower()
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./scorecheck.db").strip()

_timeout_value = os.environ.get("SCORECHECK_UPSTREAM_TIMEOUT_SECONDS", "4.0").strip()
try:
    UPSTREAM_TIMEOUT_SECONDS = max(1.0, float(_timeout_value))
except ValueError:
    UPSTREAM_TIMEOUT_SECONDS = 4.0

# Database setup
Base = declarative_base()
engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args=({"check_same_thread": False} if "sqlite" in DATABASE_URL else {}),
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class ApiCache(Base):
    __tablename__ = "api_cache"
    cache_key = Column(String, primary_key=True, index=True)
    payload = Column(Text, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


Base.metadata.create_all(bind=engine)

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

TEAM_SEARCH_ALIASES: Dict[tuple[str, str], List[str]] = {
    ("nhl", "utah-mammoth"): ["Utah Hockey Club", "Arizona Coyotes"],
    ("mlb", "oakland-athletics"): ["Athletics", "Sacramento Athletics"],
}

LEAGUE_TEAMS_CACHE: Dict[str, Dict[str, Any]] = {}
LEAGUE_TEAMS_TTL_SECONDS = 3600
LEAGUES_TTL_SECONDS = 300
LEAGUE_TEAM_DETAILS_TTL_SECONDS = 300
GAME_PLAYERS_TTL_SECONDS = 300
TODAY_GAMES_TTL_SECONDS = 30

DB_CACHE_ENABLED = True
logger.info("Database cache enabled using SQLAlchemy.")


def _active_season_for_league(league_name: str) -> str:
    now = datetime.now(timezone.utc)
    year = now.year
    month = now.month

    if league_name in ("NBA", "NHL"):
        if month >= 9:
            return f"{year}-{year + 1}"
        return f"{year - 1}-{year}"

    if league_name == "MLB":
        if month < 3:
            return str(year - 1)
        return str(year)

    return DEFAULT_SEASON


def _cache_get_json(cache_key: str) -> Optional[Any]:
    """Get cached data from SQLite/PostgreSQL."""
    try:
        session = SessionLocal()
        cache_entry = (
            session.query(ApiCache)
            .filter(
                ApiCache.cache_key == cache_key,
                ApiCache.expires_at > datetime.now(timezone.utc),
            )
            .first()
        )
        session.close()
        if not cache_entry:
            return None
        return json.loads(cache_entry.payload)
    except Exception as e:
        logger.warning(f"Cache get failed for {cache_key}: {e}")
        return None


def _cache_set_json(cache_key: str, payload: Any, ttl_seconds: int) -> None:
    """Set cached data in SQLite/PostgreSQL."""
    try:
        session = SessionLocal()
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
        cache_entry = (
            session.query(ApiCache).filter(ApiCache.cache_key == cache_key).first()
        )

        if cache_entry:
            cache_entry.payload = json.dumps(payload)
            cache_entry.expires_at = expires_at
            cache_entry.updated_at = datetime.now(timezone.utc)
        else:
            cache_entry = ApiCache(
                cache_key=cache_key,
                payload=json.dumps(payload),
                expires_at=expires_at,
                updated_at=datetime.now(timezone.utc),
            )
            session.add(cache_entry)

        session.commit()
        session.close()
    except Exception as e:
        logger.warning(f"Cache set failed for {cache_key}: {e}")
        session.close()


def _slugify(value: str) -> str:
    import re

    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug


def _merge_players(
    base_players: List[Dict[str, Any]], extra_players: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    merged: Dict[str, Dict[str, Any]] = {
        player["name"]: player for player in base_players if player.get("name")
    }
    for player in extra_players:
        name = player.get("name")
        if not name or name in merged:
            continue
        merged[name] = player
    return list(merged.values())


def _team_search_candidates(league_key: str, team_name: str) -> List[str]:
    base_name = str(team_name or "").strip()
    if not base_name:
        return []

    alias_key = (league_key, _slugify(base_name))
    aliases = TEAM_SEARCH_ALIASES.get(alias_key, [])

    candidates: List[str] = []
    seen = set()
    for candidate in [base_name, *aliases]:
        cleaned = str(candidate or "").strip()
        if not cleaned:
            continue
        normalized = _slugify(cleaned)
        if normalized in seen:
            continue
        seen.add(normalized)
        candidates.append(cleaned)

    return candidates


def _logo_for_team(
    logos_by_name: Dict[str, str], league_key: str, team_name: str
) -> str:
    for candidate in _team_search_candidates(league_key, team_name):
        logo = logos_by_name.get(candidate.lower())
        if logo:
            return logo
    return ""


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
                    "position": position.get("abbreviation")
                    or position.get("name")
                    or "-",
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
                    "position": position.get("abbreviation")
                    or position.get("name")
                    or "-",
                    "stats": {},
                }
            )
        return players
    except Exception:
        return []


def _static_league_teams() -> Dict[str, List[Dict[str, Any]]]:
    nba_teams = [
        "Atlanta Hawks",
        "Boston Celtics",
        "Brooklyn Nets",
        "Charlotte Hornets",
        "Chicago Bulls",
        "Cleveland Cavaliers",
        "Dallas Mavericks",
        "Denver Nuggets",
        "Detroit Pistons",
        "Golden State Warriors",
        "Houston Rockets",
        "Indiana Pacers",
        "LA Clippers",
        "Los Angeles Lakers",
        "Memphis Grizzlies",
        "Miami Heat",
        "Milwaukee Bucks",
        "Minnesota Timberwolves",
        "New Orleans Pelicans",
        "New York Knicks",
        "Oklahoma City Thunder",
        "Orlando Magic",
        "Philadelphia 76ers",
        "Phoenix Suns",
        "Portland Trail Blazers",
        "Sacramento Kings",
        "San Antonio Spurs",
        "Toronto Raptors",
        "Utah Jazz",
        "Washington Wizards",
    ]

    nhl_teams = [
        "Anaheim Ducks",
        "Utah Mammoth",
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
        "nba": [
            {"id": _slugify(name), "name": name, "league": "NBA"}
            for name in sorted(nba_teams)
        ],
        "nhl": [
            {"id": _slugify(name), "name": name, "league": "NHL"}
            for name in sorted(nhl_teams)
        ],
        "mlb": [
            {"id": _slugify(name), "name": name, "league": "MLB"}
            for name in sorted(mlb_teams)
        ],
    }


def _fetch_thesportsdb_league_teams(league_name: str) -> List[Dict[str, Any]]:
    connector = TheSportsDBConnector(timeout_seconds=UPSTREAM_TIMEOUT_SECONDS)

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


def _fetch_espn_team_logos(league_name: str) -> Dict[str, str]:
    connector = ESPNConnector(
        league_name=league_name,
        timeout_seconds=UPSTREAM_TIMEOUT_SECONDS,
    )

    data = connector.get_teams(season=DEFAULT_SEASON)
    response = data.get("response") if isinstance(data, dict) else None
    if not isinstance(response, list):
        return {}

    team_logos: Dict[str, str] = {}
    for item in response:
        if not isinstance(item, dict):
            continue
        team = item.get("team") if isinstance(item.get("team"), dict) else item
        if not isinstance(team, dict):
            continue

        team_name = str(team.get("displayName") or team.get("name") or "").strip()
        if not team_name:
            continue

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
                league_code = str(connector._path_info.get("league") or "")
                logo = (
                    f"https://a.espncdn.com/i/teamlogos/{league_code}/500/"
                    f"scoreboard/{abbreviation}.png"
                )

        team_logos[team_name.lower()] = logo

    return team_logos


@app.get("/api/health")
def health_check() -> dict:
    return {"status": "ok"}


@app.get("/api/leagues")
def get_leagues() -> dict:
    cache_key = f"leagues:{SPORTS_DATA_SOURCE}:{DEFAULT_SEASON}"
    cached_response = _cache_get_json(cache_key)
    if isinstance(cached_response, dict):
        return cached_response

    leagues = []
    static_teams = _static_league_teams()
    for league_id, config in LEAGUE_CONFIG.items():
        available = True
        if SPORTS_DATA_SOURCE == "thesportsdb":
            available = bool(config.get("thesportsdb")) or bool(
                static_teams.get(league_id)
            )
        leagues.append(
            {
                "id": league_id,
                "name": config["name"],
                "available": available,
            }
        )
    response = {"leagues": leagues}
    _cache_set_json(cache_key, response, LEAGUES_TTL_SECONDS)
    return response


@app.get("/api/leagues/{league_id}/teams")
def get_league_teams(league_id: str) -> dict:
    league_key = league_id.lower().strip()
    cache_key = (
        f"league_teams:v2:{SPORTS_DATA_SOURCE}:{league_key}:{DEFAULT_SEASON}"
    )
    cached_response = _cache_get_json(cache_key)
    if isinstance(cached_response, dict):
        return cached_response

    config = LEAGUE_CONFIG.get(league_key)
    if not config:
        raise HTTPException(status_code=404, detail="League not found")

    static_teams = _static_league_teams().get(league_key)
    if static_teams:
        teams = [dict(team) for team in static_teams]
        source = "static"

        if SPORTS_DATA_SOURCE == "espn":
            try:
                logos_by_name = _fetch_espn_team_logos(config["name"])
                for team in teams:
                    team_name = str(team.get("name") or "")
                    team["logo"] = _logo_for_team(logos_by_name, league_key, team_name)
                source = "espn"
            except Exception as exc:
                logger.warning(
                    "Failed to enrich league teams with ESPN logos "
                    f"for {league_key}: {exc}"
                )

        response = {
            "league": config["name"],
            "teams": teams,
            "source": source,
        }
        _cache_set_json(cache_key, response, LEAGUE_TEAMS_TTL_SECONDS)
        return response

    if SPORTS_DATA_SOURCE != "thesportsdb":
        raise HTTPException(
            status_code=400,
            detail="League team listing is only supported with TheSportsDB",
        )

    league_name = config.get("thesportsdb")
    if not league_name:
        raise HTTPException(
            status_code=400,
            detail=f"League {config['name']} is not available via TheSportsDB",
        )

    cached = LEAGUE_TEAMS_CACHE.get(league_key)
    if cached and time.time() - cached["timestamp"] < LEAGUE_TEAMS_TTL_SECONDS:
        teams = cached["teams"]
    else:
        try:
            teams = _fetch_thesportsdb_league_teams(league_name)
            LEAGUE_TEAMS_CACHE[league_key] = {
                "timestamp": time.time(),
                "teams": teams,
            }
        except TheSportsDBError as exc:
            if "429" in str(exc) and cached:
                logger.warning(
                    f"Rate limited while fetching {league_name}; serving cached data."
                )
                teams = cached["teams"]
            else:
                raise HTTPException(
                    status_code=429,
                    detail="Rate limited by TheSportsDB. Please retry.",
                )
    response = {
        "league": config["name"],
        "teams": teams,
        "source": SPORTS_DATA_SOURCE,
    }
    _cache_set_json(cache_key, response, LEAGUE_TEAMS_TTL_SECONDS)
    return response


@app.get("/api/games/today")
def get_today_games(include_yesterday: bool = True) -> dict:
    now_et = datetime.now(ZoneInfo("America/New_York"))
    today_key = now_et.strftime("%Y%m%d")
    yesterday_key = (now_et - timedelta(days=1)).strftime("%Y%m%d")
    yesterday_date = (now_et - timedelta(days=1)).date().isoformat()
    include_yesterday_flag = int(include_yesterday)
    cache_key = (
        f"today_games:espn:{today_key}:"
        f"include_yesterday:{include_yesterday_flag}"
    )
    cached_response = _cache_get_json(cache_key)
    if isinstance(cached_response, dict):
        return cached_response

    today_leagues: List[Dict[str, Any]] = []
    yesterday_leagues: List[Dict[str, Any]] = []
    for league_id, config in LEAGUE_CONFIG.items():
        connector = ESPNConnector(
            league_name=config["name"],
            timeout_seconds=UPSTREAM_TIMEOUT_SECONDS,
        )
        today_games: List[Dict[str, Any]] = []
        yesterday_games: List[Dict[str, Any]] = []
        try:
            scoreboard = connector.get_scoreboard(date=today_key)
            today_games = connector.extract_scoreboard_games(scoreboard)
        except Exception as exc:
            logger.warning(
                f"Failed to fetch today's games for {league_id}: {exc}"
            )

        if include_yesterday:
            try:
                yesterday_scoreboard = connector.get_scoreboard(
                    date=yesterday_key
                )
                yesterday_games = connector.extract_scoreboard_games(
                    yesterday_scoreboard
                )
            except Exception as exc:
                logger.warning(
                    f"Failed to fetch yesterday's games for {league_id}: {exc}"
                )

        today_leagues.append(
            {
                "id": league_id,
                "name": config["name"],
                "games": today_games,
            }
        )
        yesterday_leagues.append(
            {
                "id": league_id,
                "name": config["name"],
                "games": yesterday_games,
            }
        )

    response = {
        "date": now_et.date().isoformat(),
        "today_key": today_key,
        "yesterday_key": yesterday_key,
        "include_yesterday": include_yesterday,
        "source": "espn",
        "today": {
            "date": now_et.date().isoformat(),
            "key": today_key,
            "leagues": today_leagues,
        },
        "yesterday": {
            "date": yesterday_date,
            "key": yesterday_key,
            "leagues": yesterday_leagues,
        },
        "leagues": today_leagues,
    }
    _cache_set_json(cache_key, response, TODAY_GAMES_TTL_SECONDS)
    return response


@app.get("/api/leagues/{league_id}/teams/{team_id}")
def get_league_team(league_id: str, team_id: str) -> dict:
    league_key = league_id.lower().strip()
    cache_key = (
        f"league_team:v3:{SPORTS_DATA_SOURCE}:{league_key}:{team_id}:{DEFAULT_SEASON}"
    )
    cached_response = _cache_get_json(cache_key)
    if isinstance(cached_response, dict):
        return cached_response

    config = LEAGUE_CONFIG.get(league_key)
    if not config:
        raise HTTPException(status_code=404, detail="League not found")

    if SPORTS_DATA_SOURCE not in ("thesportsdb", "espn"):
        raise HTTPException(status_code=400, detail="Unsupported data source")

    static_teams = _static_league_teams().get(league_key)
    if not static_teams:
        raise HTTPException(status_code=404, detail="League teams not found")

    matched = next((team for team in static_teams if team["id"] == team_id), None)
    if not matched:
        raise HTTPException(status_code=404, detail="Team not found")

    team_name = matched["name"]
    team_search_candidates = _team_search_candidates(league_key, team_name)
    active_season = _active_season_for_league(config["name"])

    connector_order = [SPORTS_DATA_SOURCE, "espn", "thesportsdb"]
    seen_sources = set()
    attempts: List[tuple[str, Any]] = []

    for source_name in connector_order:
        if source_name in seen_sources:
            continue
        seen_sources.add(source_name)

        if source_name == "thesportsdb" and not config.get("thesportsdb"):
            attempts.append((source_name, "league unavailable"))
            continue

        if source_name == "espn":
            connector = ESPNConnector(
                league_name=config["name"],
                timeout_seconds=UPSTREAM_TIMEOUT_SECONDS,
            )
        elif source_name == "thesportsdb":
            connector = TheSportsDBConnector(
                timeout_seconds=UPSTREAM_TIMEOUT_SECONDS
            )
        else:
            continue

        try:
            team_info = None
            resolved_search_name = team_name
            for search_name in team_search_candidates:
                team_search = connector.get_teams(
                    season=DEFAULT_SEASON, search=search_name
                )
                parsed_team = connector.extract_team(team_search)
                external_id = (parsed_team or {}).get("id")
                if external_id:
                    team_info = parsed_team
                    resolved_search_name = search_name
                    break

            external_id = (team_info or {}).get("id")
            team_logo = (team_info or {}).get("logo") or ""
            if not external_id:
                attempts.append((source_name, "team id not found"))
                continue

            resolved_team_name = str(
                (team_info or {}).get("name") or resolved_search_name or team_name
            )

            players_response = connector.get_players(
                season=active_season, team_id=external_id
            )
            games_response = connector.get_games(
                season=active_season, team_id=external_id
            )

            players = connector.extract_players(players_response)
            if config["name"] == "NHL" and len(players) < 15:
                players = _merge_players(players, _fetch_nhl_roster(resolved_team_name))
            if config["name"] == "MLB" and len(players) < 15:
                players = _merge_players(
                    players, _fetch_mlb_roster(resolved_team_name, active_season)
                )

            games = connector.extract_games(games_response, resolved_team_name)

            if not games and source_name != "espn":
                try:
                    espn_connector = ESPNConnector(
                        league_name=config["name"],
                        timeout_seconds=UPSTREAM_TIMEOUT_SECONDS,
                    )
                    fallback_searches = [
                        resolved_team_name,
                        *team_search_candidates,
                    ]
                    seen_searches = set()
                    for fallback_name in fallback_searches:
                        normalized_name = _slugify(fallback_name)
                        if normalized_name in seen_searches:
                            continue
                        seen_searches.add(normalized_name)

                        espn_team_search = espn_connector.get_teams(
                            season=active_season, search=fallback_name
                        )
                        espn_team = espn_connector.extract_team(espn_team_search)
                        espn_team_id = (espn_team or {}).get("id")
                        if not espn_team_id:
                            continue

                        espn_team_name = str(
                            (espn_team or {}).get("name") or fallback_name
                        )
                        espn_games_response = espn_connector.get_games(
                            season=active_season,
                            team_id=espn_team_id,
                        )
                        espn_games = espn_connector.extract_games(
                            espn_games_response, espn_team_name
                        )
                        if espn_games:
                            games = espn_games
                            break
                except Exception as espn_exc:
                    attempts.append(("espn-games-fallback", str(espn_exc)))

            if not players and not games:
                attempts.append((source_name, "no players or games returned"))
                continue

            response = {
                "league": config["name"],
                "id": team_id,
                "name": team_name,
                "logo": team_logo,
                "players": players,
                "games": games,
                "source": source_name,
            }
            _cache_set_json(cache_key, response, LEAGUE_TEAM_DETAILS_TTL_SECONDS)
            return response
        except Exception as exc:
            attempts.append((source_name, str(exc)))

    attempts_note = "; ".join(f"{source}: {reason}" for source, reason in attempts)
    logger.warning(
        f"Unable to fetch live team details for {team_name}. Attempts: {attempts_note}"
    )
    response = {
        "id": team_id,
        "name": team_name,
        "league": config["name"],
        "logo": matched.get("logo", ""),
        "players": [],
        "games": [],
        "source": "static",
        "warning": "Live team details temporarily unavailable",
    }
    _cache_set_json(cache_key, response, LEAGUE_TEAM_DETAILS_TTL_SECONDS)
    return response


@app.get("/api/leagues/{league_id}/teams/{team_id}/games/{game_id}/players")
def get_league_team_game_players(league_id: str, team_id: str, game_id: str) -> dict:
    league_key = league_id.lower().strip()
    cache_key = f"game_players:{SPORTS_DATA_SOURCE}:{league_key}:{team_id}:{game_id}"
    cached_response = _cache_get_json(cache_key)
    if isinstance(cached_response, dict):
        return cached_response

    config = LEAGUE_CONFIG.get(league_key)
    if not config:
        raise HTTPException(status_code=404, detail="League not found")

    if SPORTS_DATA_SOURCE != "thesportsdb":
        raise HTTPException(
            status_code=400,
            detail="Per-game player stats are only supported with TheSportsDB",
        )

    if not game_id:
        raise HTTPException(status_code=400, detail="Game id is required")

    connector = TheSportsDBConnector(timeout_seconds=UPSTREAM_TIMEOUT_SECONDS)
    event_stats_data = connector.get_event_stats(game_id)
    players = connector.extract_event_player_stats(event_stats_data)

    response = {
        "league": config["name"],
        "team_id": team_id,
        "game_id": game_id,
        "players": players,
        "available": len(players) > 0,
        "source": SPORTS_DATA_SOURCE,
    }
    _cache_set_json(cache_key, response, GAME_PLAYERS_TTL_SECONDS)
    return response
