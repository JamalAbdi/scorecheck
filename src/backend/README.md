# Backend (FastAPI)

## Install
```
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

## Tests
```
pip install -r requirements-dev.txt
pytest -q
```

## Run
```
uvicorn main:app --reload --port 8000
```

## Environment variables
- APISPORTS_KEY: API-Sports key used to fetch live data
- APISPORTS_SEASON: default season (e.g. 2024)
- APISPORTS_NBA_SEASON / APISPORTS_NHL_SEASON / APISPORTS_MLB_SEASON: override per league

Health check: http://localhost:8000/api/health
Teams: http://localhost:8000/api/teams
Team details: http://localhost:8000/api/teams/{team_id}
