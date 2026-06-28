# Disha (दिशा) — JEE College Recommender · a UTMT initiative

An open-source intelligent pipeline deployed as a **unified FastAPI portal** that
suggests institutes and branches based on JEE Main / Advanced rank.

Built for **[UTMT](https://www.utmt.org)** ("Learn to Build AI Products") and designed
to be deployed on the UTMT platform. The frontend is plain HTML + CSS + vanilla JS
(no frameworks), presented as **Disha** — a calm, guided counselling experience for
JEE aspirants. It also surfaces UTMT's
[Nachiketa Initiative](https://www.utmt.org/nachiketa) to eligible students
(90+ percentile, family income below ₹3 lakh).

Portal **and** JSON API are served from the same process on the same port — no
separate frontend server required.

---

## What it does

- Accepts JEE Main rank (for NIT / IIIT / GFTI) and / or JEE Advanced rank (for IIT).
- Filters 2,410 JoSAA 2025 OPEN (CRL) cutoff rows by rank, gender pool, home-state
  quota (HS/OS/AI/special) and career interest.
- Groups results into **Target** (within last year's opening-closing window),
  **Reach** (just beyond closing, ≤ 25 % above) and **Safe** (rank beats opening).
- Re-ranks branches by stated career goal (coding, research, MBA/management, core
  engineering, or undecided) using a tag-weight scoring model.
- Returns overall guidance, category blurbs, institute-type breakdown and a star (★)
  on cards that match your interest.
- Reservation category selector is present in the UI; OBC-NCL / SC / ST / EWS / PwD
  cutoff data will be loaded once a multi-category dataset is available.

---

## Quick start — one command

```bash
# From the repo root
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```

Alternatively, on Windows, you can double-click `run.bat` to automatically install dependencies and run the server.

Then open **http://127.0.0.1:8000** — the portal and API are on the same origin.

Interactive API docs are at **http://127.0.0.1:8000/api/docs**.

---

## Docker (single command)

```bash
# Build and run
docker compose up --build

# Or with plain Docker
docker build -t jee-recommender .
docker run -p 8000:8000 jee-recommender
```

Open **http://localhost:8000**.

---

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/`  | Portal (serves `index.html`) |
| `GET`  | `/api/health` | Health check + program count |
| `GET`  | `/api/meta` | States, goals, genders, categories, dataset size |
| `POST` | `/api/recommend` | Recommendation pipeline |
| `GET`  | `/api/docs` | Interactive Swagger UI |

### POST `/api/recommend` — request body

```json
{
  "adv_rank":   1500,
  "mains_rank": 6000,
  "gender":     "male",
  "home_state": "Rajasthan",
  "goal":       "coding",
  "seat_category": "OPEN",
  "max_results": 90
}
```

- `adv_rank` and `mains_rank` — at least one is required.
- `goal` — `coding` | `research` | `mba` | `core` | `undecided`.
- `seat_category` — `OPEN` (current dataset); other categories listed in `/api/meta`.
- `max_results` — 1–300, default 60.

---

## Project structure

```
.
├── app/
│   ├── __init__.py
│   └── disha/               # Backend modules
│       ├── __init__.py
│       ├── config.py        # Env-based settings (CORS, data path)
│       ├── data_loader.py   # Excel -> Program dataclasses (cached)
│       ├── recommender.py   # Pipeline: filter -> categorise -> rank
│       ├── schemas.py       # Pydantic request/response models
│       ├── states.py        # States, quotas, branch tags, goal weights
│       └── data/
│           └── JEE_2025_Cutoffs.xlsx
├── templates/
│   └── disha_templates/     # Frontend resources
│       ├── assets/
│       │   └── favicon.svg
│       ├── css/
│       │   └── style.css
│       ├── js/
│       │   ├── api.js
│       │   ├── app.js
│       │   ├── config.js
│       │   └── i18n.js
│       ├── index.html
│       ├── manifest.json
│       └── sw.js
├── tests/                   # Test suite
│   ├── test_api.py
│   └── test_recommender.py
├── .env.example
├── .gitignore
├── conftest.py
├── LICENSE
├── main.py                  # FastAPI app — serves API + portal
├── README.md
├── render.yaml
├── requirements.txt
└── run.bat
```

---

## Recommendation pipeline

```
Excel (2 410 rows)
  └─ data_loader   →  Program dataclasses (cached, parsed once at startup)
       └─ recommender
            ├─ filter by: rank type (Advanced=IIT / Mains=rest)
            │             gender pool (neutral | female)
            │             quota (AI / HS / OS / GO / JK / LA)
            ├─ categorise: Safe / Target / Reach  (or drop if too far)
            ├─ score: tag-weight model per career goal + institute brand bonus
            └─ sort: category → score desc → closing rank → name
```

---

## Configuration

| Env variable | Default | Description |
|-------------|---------|-------------|
| `CORS_ORIGINS` | `http://localhost:8000,...` | Comma-separated allowed origins |
| `DATA_PATH` | `data/JEE_2025_Cutoffs.xlsx` | Path to cutoff workbook |

Copy `backend/.env.example` → `backend/.env` and adjust values.

---

## Running tests

```bash
cd backend
source .venv/bin/activate
pytest tests/ -v
```

---

## Data

Cutoffs are sourced from the
[atmabodha/OpenNLP JEE dataset](https://github.com/atmabodha/OpenNLP)
(JoSAA 2025, OPEN CRL, Round 6 closing ranks), published by UTMT.
This tool is for guidance only and does not guarantee admission outcomes.

---

## License

MIT © 2026
