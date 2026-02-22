# scorecheck

## Backend (FastAPI)
From [src/backend](src/backend):
```
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

For live data, set APISPORTS_KEY before running the backend.

API endpoints:
- http://localhost:8000/api/health
- http://localhost:8000/api/teams
- http://localhost:8000/api/teams/{team_id}

## Project setup
```
npm install
```

### Compiles and hot-reloads for development
```
npm run serve
```

### Compiles and minifies for production
```
npm run build
```

### Lints and fixes files
```
npm run lint
```

### Customize configuration
See [Configuration Reference](https://cli.vuejs.org/config/).
