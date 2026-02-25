from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta

import requests

from .base import BaseSportDataConnector, SportsDataError

Json = Dict[str, Any]


class TheSportsDBError(SportsDataError):
    """TheSportsDB connector errors."""


class TheSportsDBConnector(BaseSportDataConnector):
    """
    Connector for TheSportsDB API.
    
    Free sports database with no authentication required.
    Supports NBA, NHL, MLB, etc.
    
    API: https://www.thesportsdb.com/api.php
    """

    BASE_URL = "https://www.thesportsdb.com/api/v1/json/123"

    def __init__(
        self,
        *,
        timeout_seconds: float = 20.0,
        session: Optional[requests.Session] = None,
        user_agent: str = "scorecheck-api/1.0",
    ) -> None:
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
        """Make GET request to TheSportsDB."""
        url = f"{self._base_url}{endpoint}"
        params_dict = dict(params or {})

        try:
            for attempt in range(3):
                resp = self._session.get(
                    url,
                    headers=self._headers(),
                    params=params_dict,
                    timeout=self._timeout,
                )
                if resp.status_code == 429 and attempt < 2:
                    retry_after = resp.headers.get("Retry-After")
                    try:
                        wait_seconds = float(retry_after) if retry_after else 1.0
                    except ValueError:
                        wait_seconds = 1.0
                    import time
                    time.sleep(wait_seconds)
                    continue
                resp.raise_for_status()
                
                # Handle empty response
                if not resp.text or resp.text.strip() == "":
                    return {}
                
                data = resp.json()
                return data
        except requests.RequestException as exc:
            raise TheSportsDBError(f"Request failed: {exc}") from exc
        except Exception as exc:
            raise TheSportsDBError(f"Failed to parse response: {exc}") from exc

    def get_teams(self, season: str, search: Optional[str] = None) -> Json:
        """Search for teams using searchteams.php endpoint."""
        if search:
            return self._get("/searchteams.php", params={"t": search})
        return {}

    def get_teams_by_league(self, league_name: str) -> Json:
        """Fetch all teams for a league using search_all_teams.php."""
        if league_name:
            return self._get("/search_all_teams.php", params={"l": league_name})
        return {}

    def get_team_by_id(self, team_id: Optional[int]) -> Json:
        """Fetch team info using lookupteam.php."""
        if team_id:
            return self._get("/lookupteam.php", params={"id": team_id})
        return {}

    def get_players(self, season: str, team_id: Optional[int] = None, search: Optional[str] = None) -> Json:
        """Fetch players for a team using lookup_all_players.php."""
        if team_id:
            return self._get("/lookup_all_players.php", params={"id": team_id})
        return {}

    def get_games(self, season: str, team_id: Optional[int] = None, date: Optional[str] = None, search: Optional[str] = None) -> Json:
        """Fetch games/events using eventslast.php."""
        if team_id:
            return self._get("/eventslast.php", params={"id": team_id})
        return {}

    def extract_team(self, data: Json) -> Optional[Dict[str, Any]]:
        """Extract team info from TheSportsDB response."""
        # searchteams.php returns {"teams": [...]}
        teams = data.get("teams")
        if isinstance(teams, list) and teams:
            first = teams[0]
            if isinstance(first, dict):
                return {
                    "id": first.get("idTeam"),
                    "name": first.get("strTeam"),
                }
        return None

    def extract_teams(self, data: Json) -> List[Dict[str, Any]]:
        """Extract team list from TheSportsDB response."""
        teams = data.get("teams")
        if not isinstance(teams, list):
            return []

        result: List[Dict[str, Any]] = []
        for item in teams:
            if not isinstance(item, dict):
                continue
            team_id = item.get("idTeam")
            name = item.get("strTeam")
            league = item.get("strLeague")
            if not team_id or not name:
                continue
            result.append(
                {
                    "id": team_id,
                    "name": name,
                    "league": league,
                }
            )

        result.sort(key=lambda t: t["name"])
        return result

    def extract_players(self, data: Json) -> List[Dict[str, Any]]:
        """Extract players from TheSportsDB response."""
        # lookup_all_players.php returns {"player": [...]}
        results = data.get("player")
        if not isinstance(results, list):
            return []

        players: List[Dict[str, Any]] = []
        seen_names = set()

        for item in results:
            if not isinstance(item, dict):
                continue

            player_name = item.get("strPlayer")
            if not player_name or player_name in seen_names:
                continue
            seen_names.add(player_name)

            position = item.get("strPosition") or "-"
            stats: Dict[str, Any] = {}

            # Extract available stats
            if item.get("intCaps"):
                stats["caps"] = item.get("intCaps")
            if item.get("intGoals"):
                stats["goals"] = item.get("intGoals")
            if item.get("strHeight"):
                stats["height"] = item.get("strHeight")
            if item.get("strWeight"):
                stats["weight"] = item.get("strWeight")

            players.append(
                {
                    "name": player_name,
                    "position": position,
                    "stats": stats,
                }
            )

        return players[:50]

    def extract_games(self, data: Json, team_name: str) -> List[Dict[str, Any]]:
        """Extract games/events from TheSportsDB response."""
        # eventslast.php returns {"results": [...]}
        results = data.get("results")
        if not isinstance(results, list):
            return []

        # Filter for games within last 4 weeks and next 2 weeks
        today = datetime.now().date()
        four_weeks_ago = today - timedelta(days=28)
        two_weeks_future = today + timedelta(days=14)

        import logging
        logger = logging.getLogger(__name__)
        logger.debug(f"extract_games: today={today}, range={four_weeks_ago} to {two_weeks_future}, team_name={team_name}")

        games: List[Dict[str, Any]] = []

        for item in results:
            if not isinstance(item, dict):
                continue

            date_str = item.get("dateEvent")
            if not date_str:
                continue

            # Parse date
            try:
                game_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                logger.debug(f"  Game date: {game_date}")
            except (ValueError, TypeError):
                logger.debug(f"  Failed to parse date: {date_str}")
                continue

            # Filter by date range
            if not (four_weeks_ago <= game_date <= two_weeks_future):
                logger.debug(f"  Game {game_date} outside range")
                continue

            home_team = item.get("strHomeTeam")
            away_team = item.get("strAwayTeam")

            if not all([date_str, home_team, away_team]):
                continue

            home = None
            opponent = None

            if team_name.lower() == home_team.lower():
                home = True
                opponent = away_team
            elif team_name.lower() == away_team.lower():
                home = False
                opponent = home_team

            home_score_str = item.get("intHomeScore")
            away_score_str = item.get("intAwayScore")

            score = None
            status = "upcoming"

            if home_score_str is not None and away_score_str is not None:
                try:
                    score = f"{int(home_score_str)}-{int(away_score_str)}"
                    status = "played"
                except (ValueError, TypeError):
                    pass

            games.append(
                {
                    "date": date_str,
                    "opponent": opponent or "TBD",
                    "home": bool(home) if home is not None else False,
                    "status": status,
                    "score": score,
                }
            )

        played_games = [game for game in games if game.get("status") == "played"]
        played_games.sort(key=lambda g: g["date"], reverse=True)
        played_games = played_games[:30]
        logger.debug(f"extract_games: returning {len(played_games)} games")
        return played_games
