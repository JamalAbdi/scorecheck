import time

import responses

from src.backend.sports_data.api_sports import ApiSportsAuthError, ApiSportsConnector, ApiSportsResponseError


@responses.activate
def test_api_sports_get_success():
    base_url = "https://example.api"
    connector = ApiSportsConnector("test-key", base_url=base_url)

    responses.add(
        responses.GET,
        f"{base_url}/status",
        json={"response": [{"status": "ok"}]},
        status=200,
    )

    result = connector._get("/status")
    assert result["response"][0]["status"] == "ok"


@responses.activate
def test_api_sports_rate_limit_then_success(monkeypatch):
    base_url = "https://example.api"
    connector = ApiSportsConnector("test-key", base_url=base_url)

    responses.add(
        responses.GET,
        f"{base_url}/teams",
        status=429,
        headers={"Retry-After": "0"},
    )
    responses.add(
        responses.GET,
        f"{base_url}/teams",
        json={"response": [{"id": 1, "name": "Team"}]},
        status=200,
    )

    monkeypatch.setattr(time, "sleep", lambda _: None)
    result = connector.get_teams("2024")
    assert result["response"][0]["name"] == "Team"


@responses.activate
def test_api_sports_auth_error():
    base_url = "https://example.api"
    connector = ApiSportsConnector("test-key", base_url=base_url)

    responses.add(
        responses.GET,
        f"{base_url}/status",
        status=401,
    )

    try:
        connector._get("/status")
        assert False, "Expected auth error"
    except ApiSportsAuthError:
        assert True


@responses.activate
def test_api_sports_response_error_on_errors_field():
    base_url = "https://example.api"
    connector = ApiSportsConnector("test-key", base_url=base_url)

    responses.add(
        responses.GET,
        f"{base_url}/status",
        json={"errors": {"request": "invalid"}},
        status=200,
    )

    try:
        connector._get("/status")
        assert False, "Expected response error"
    except ApiSportsResponseError:
        assert True
