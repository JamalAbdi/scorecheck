import pytest

from src.backend.sports_data.thesportsdb import TheSportsDBConnector, TheSportsDBError


def test_thesportsdb_get_teams_search():
    """Integration test: fetch real teams data from TheSportsDB."""
    connector = TheSportsDBConnector()
    
    # Search for Toronto Raptors
    result = connector.get_teams("2024", search="Toronto Raptors")
    
    # Should get some results back
    assert result is not None
    assert isinstance(result, dict)


def test_thesportsdb_extract_team_from_real_data():
    """Integration test: extract team from real API response."""
    connector = TheSportsDBConnector()
    
    # Fetch real data
    data = connector.get_teams("2024", search="Toronto Raptors")
    
    # Extract team
    team = connector.extract_team(data)
    
    # Should extract something if data exists
    if data.get("results"):
        assert team is not None
        assert "name" in team or "strTeam" in (data.get("results")[0] if data.get("results") else {})


def test_thesportsdb_extract_players_from_real_data():
    """Integration test: extract players from real API response."""
    connector = TheSportsDBConnector()
    
    # Try to get player data (may not always return results)
    # Using a generic search that should return something
    result = connector.get_players("2024", search="Toronto")
    
    players = connector.extract_players(result)
    
    # Should return a list (may be empty)
    assert isinstance(players, list)


def test_thesportsdb_extract_games_from_real_data():
    """Integration test: extract games from real API response."""
    connector = TheSportsDBConnector()
    
    # Get games data
    result = connector.get_games("2024", search="Toronto Raptors")
    
    games = connector.extract_games(result, "Toronto Raptors")
    
    # Should return a list
    assert isinstance(games, list)
    
    # If games exist, they should have required fields
    if games:
        for game in games:
            assert "date" in game
            assert "opponent" in game
            assert "home" in game
            assert "status" in game
            assert "score" in game


def test_thesportsdb_null_results_handling():
    """Integration test: handle no results gracefully."""
    connector = TheSportsDBConnector()
    
    # Search for something that won't return results
    result = connector.get_teams("2024", search="XYZNonexistentTeamXYZ")
    
    # Should either return empty response or handle gracefully
    assert result is not None
    assert isinstance(result, dict)


def test_thesportsdb_connector_timeout():
    """Integration test: connector should handle timeouts."""
    # Create connector with very short timeout
    connector = TheSportsDBConnector(timeout_seconds=0.001)
    
    # This should timeout or fail gracefully
    try:
        result = connector.get_teams("2024", search="Toronto")
        # If it succeeds despite short timeout, that's fine
        assert isinstance(result, dict)
    except TheSportsDBError:
        # Expected on timeout
        assert True

