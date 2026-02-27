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
- SPORTS_DATA_SOURCE: `espn` (default) or `thesportsdb`

## Data Sources

### TheSportsDB (alternative)
- No API key required
- Free public sports database
- Supported sports: various
```
export SPORTS_DATA_SOURCE=thesportsdb
uvicorn main:app --reload --port 8000
```

### ESPN (default)
- No API key required
- Public JSON endpoints for NBA/NHL/MLB team rosters and schedules
```
export SPORTS_DATA_SOURCE=espn
uvicorn main:app --reload --port 8000
```

API endpoints:
- http://localhost:8000/api/health
- http://localhost:8000/api/leagues
- http://localhost:8000/api/leagues/{league_id}/teams
- http://localhost:8000/api/leagues/{league_id}/teams/{team_id}
