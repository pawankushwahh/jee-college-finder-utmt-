# Backend — JEE College Recommender API

FastAPI service that powers the recommendation engine. It exposes a JSON API
only; the user interface lives in the sibling [`frontend/`](../frontend)
project and talks to this service over HTTP.

## API

| Method | Path             | Description                                          |
| ------ | ---------------- | ---------------------------------------------------- |
| GET    | `/api/health`    | Liveness check + dataset size                        |
| GET    | `/api/meta`      | Form metadata: states, goals, genders, dataset size  |
| POST   | `/api/recommend` | Filtered, categorized, interest-ranked suggestions   |
| GET    | `/docs`          | Interactive OpenAPI documentation                    |

### Example

```bash
curl -X POST http://127.0.0.1:8000/api/recommend \
  -H "Content-Type: application/json" \
  -d '{"adv_rank": 1500, "mains_rank": 6000, "gender": "female", "home_state": "Rajasthan", "goal": "coding"}'
```

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
