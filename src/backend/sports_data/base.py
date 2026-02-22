from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


Json = Dict[str, Any]


class SportsDataError(Exception):
    """Base exception for sports data connector errors."""


class BaseSportDataConnector(ABC):
    """
    Abstract base class for sports data connectors.
    
    Implementations should provide methods to fetch teams, players, and games.
    """

    @abstractmethod
    def get_teams(self, season: str, search: Optional[str] = None) -> Json:
        """Fetch teams data.
        
        Returns raw response from the API.
        """
        pass

    @abstractmethod
    def get_players(self, season: str, team_id: Optional[int] = None, search: Optional[str] = None) -> Json:
        """Fetch players data.
        
        Returns raw response from the API.
        """
        pass

    @abstractmethod
    def get_games(self, season: str, team_id: Optional[int] = None, date: Optional[str] = None, search: Optional[str] = None) -> Json:
        """Fetch games/events data.
        
        Returns raw response from the API.
        """
        pass

    @abstractmethod
    def extract_team(self, data: Json) -> Optional[Dict[str, Any]]:
        """Extract a single team from API response."""
        pass

    @abstractmethod
    def extract_players(self, data: Json) -> List[Dict[str, Any]]:
        """Extract players list from API response."""
        pass

    @abstractmethod
    def extract_games(self, data: Json, team_name: str) -> List[Dict[str, Any]]:
        """Extract games/events list from API response."""
        pass
