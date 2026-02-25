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
- APISPORTS_KEY: API-Sports key for live data (get free key at https://api-sports.io)
- APISPORTS_SEASON: default season (e.g. 2024)
- APISPORTS_NBA_SEASON / APISPORTS_NHL_SEASON / APISPORTS_MLB_SEASON: override per league
- SPORTS_DATA_SOURCE: `api-sports` (default, requires key) or `thesportsdb` (free, no key)

## Data Sources

### API-Sports (default)
- Requires API key (free tier available)
- More comprehensive data
- Supports MLB, NBA, NHL
```
export APISPORTS_KEY="your-key-here"
uvicorn main:app --reload --port 8000
```

### TheSportsDB (alternative)
- No API key required
- Free public sports database
- Supported sports: various
```
export SPORTS_DATA_SOURCE=thesportsdb
uvicorn main:app --reload --port 8000
```

API endpoints:
- http://localhost:8000/api/health
- http://localhost:8000/api/teams
- http://localhost:8000/api/teams/{team_id}
