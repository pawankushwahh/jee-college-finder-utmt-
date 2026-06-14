# Backend — JEE College Recommender API

FastAPI service that powers the recommendation engine. It exposes a JSON API
only; the user interface lives in the sibling [`frontend/`](../frontend)
project and talks to this service over HTTP.

## API

| Method | Path             | Description                                          |
| ------ | ---------------- | ---------------------------------------------------- |
| GET    | `/api/health`    | Liveness check + dataset size                        |
| GET    | `/api/meta`      | Form metadata: states, goals, genders, branches, size |
| POST   | `/api/recommend` | Filtered, categorized, interest-ranked suggestions   |
| GET    | `/docs`          | Interactive OpenAPI documentation                    |

### Example

```bash
curl -X POST http://127.0.0.1:8000/api/recommend \
  -H "Content-Type: application/json" \
  -d '{"adv_rank": 1500, "mains_rank": 6000, "gender": "female", "home_state": "Rajasthan", "goal": "coding"}'
```

### Branch preferences

`/api/recommend` accepts an optional `"branch_preferences"` array to filter
results to specific branch families (e.g. `["cs_it", "ece"]`). An empty list (or
only `"any"`) shows every eligible branch. The available values and their labels
are returned by `/api/meta` under `branches`; each value maps to one or more
branch tags from `classify_branch` (see `app/states.py`, `BRANCH_PREFERENCES`).

### Language

`/api/recommend` accepts an optional `"lang"` field (`"en"` default, or `"hi"`).
When `"hi"` is sent, all generated text — `guidance`, `interest_guidance`,
category `blurb`s, `notes`, `fit_label`s and per-card `reason`s — is returned in
Hindi (Devanagari), with technical terms (CSE, NIT, Target/Reach/Safe) kept in
English. Translations live alongside their English originals in
[`app/recommender.py`](app/recommender.py) and
[`app/states.py`](app/states.py) (`GOAL_GUIDANCE`).

## Configuration

Settings are read from environment variables (or a local `.env` file —
see `.env.example`):

| Variable       | Default                                         | Purpose                                  |
| -------------- | ----------------------------------------------- | ---------------------------------------- |
| `CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173`   | Comma-separated allowed frontend origins |
| `DATA_PATH`    | `data/JEE_2025_Cutoffs.xlsx`                    | Cutoff workbook location                 |

## Running locally

```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # on Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload    # serves on http://127.0.0.1:8000
```

## Tests

```bash
pytest
```

## Layout

```
app/
  main.py          FastAPI app + /api routes
  config.py        environment-based settings (CORS, data path)
  data_loader.py   loads + preprocesses the xlsx once at startup
  recommender.py   filtering, categorization, interest ranking, guidance
  states.py        institute -> state map + interest -> branch-tag map
  schemas.py       Pydantic request/response models
data/
  JEE_2025_Cutoffs.xlsx
tests/
  test_recommender.py   unit + pipeline tests
  test_api.py           HTTP API integration tests
```
