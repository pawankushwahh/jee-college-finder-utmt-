# Disha (दिशा) — JEE College Recommender · a UTMT initiative

An open-source intelligent pipeline deployed as a **unified FastAPI portal** that suggests institutes and branches based on JEE Main / Advanced rank, gender, home state, and career interest.

Built for **[UTMT](https://www.utmt.org)** ("Learn to Build AI Products") and designed to be deployed on the UTMT platform. The frontend is plain HTML + CSS + vanilla JS (no frameworks), presented as **Disha** — a calm, guided counselling experience for JEE aspirants. It also surfaces UTMT's [Nachiketa Initiative](https://www.utmt.org/nachiketa) to eligible students (90+ percentile, family income below ₹3 lakh).

Portal **and** JSON API are served from the same process on the same port — no separate frontend server required.

---

## Key Features (Audited)

- **Dual Data Modes**:
  - **Basic Mode**: Loads **2,410 rows** of JoSAA 2025 OPEN (CRL) Round 6 cutoffs from the Excel sheet (`JEE_2025_Cutoffs.xlsx`).
  - **Extended Mode**: Loads historical cutoffs from 2018–2025 (`merged_jee_cutoff_2018_2025.csv`) covering all reservation categories (**OBC-NCL, SC, ST, EWS, PwD, and OPEN**).
- **Statistical Admission Probability**: Calculates the exact probability of admission (0% to 100%) using a logistic Sigmoid function of the Z-score based on historical closing rank volatility (standard deviation).
- **Cutoff Stability Indicators**: Classifies cutoff confidence into **High** (spread $\ge$ 6,000 ranks), **Medium**, or **Fragile** (spread < 1,000 ranks) to warn students about volatile cutoffs.
- **Personalized Tag-Weight Scoring**: Re-ranks branches based on the student's career goal (coding, research, MBA, core engineering, or undecided) and dynamically blends this with the institute's brand tier using a **Brand-vs-Branch Priority Slider**.
- **Draggable Preference List**: Allows students to bookmark recommended options into a custom "My Preference List" drawer, rearrange them via drag-and-drop, export them as a CSV, or print them.
- **Geographic & Metro Filters**: Allows students to filter options by region (North, South, East, West, Northeast/Hills) or restrict results to major metro hubs.
- **Multi-lingual Support**: Fully localized in **English, Hindi, Gujarati, and Kannada**, with natural translations that retain common technical terms.
- **Progressive Web App (PWA)**: Includes a service worker (`sw.js`) for offline caching of the app shell and a `manifest.json` for home-screen installation.

---

## Quick Start — One Command

From the repository root, run:

```bash
# Create and activate virtual environment
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start the FastAPI server
uvicorn main:app --reload
```

Alternatively, on Windows, you can double-click `run.bat` to automatically install dependencies and run the server.

- Open **http://127.0.0.1:8000** to access the portal.
- Interactive API docs are available at **http://127.0.0.1:8000/api/docs**.

---

## Docker (Single Command)

```bash
# Build and run with Docker Compose
docker compose up --build

# Or with plain Docker
docker build -t jee-recommender .
docker run -p 8000:8000 jee-recommender
```

Open **http://localhost:8000**.

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/`  | Portal (serves `index.html`) |
| `GET`  | `/api/health` | Health check + program count |
| `GET`  | `/api/meta` | States, goals, genders, categories, branches, and dataset size |
| `POST` | `/api/recommend` | Recommendation pipeline |
| `GET`  | `/api/docs` | Interactive Swagger UI |

### POST `/api/recommend` — Request Body

```json
{
  "adv_rank": 1500,
  "mains_rank": 6000,
  "gender": "male",
  "home_state": "Rajasthan",
  "goal": "coding",
  "data_mode": "basic",
  "seat_category": "OPEN",
  "brand_branch_ratio": 0.5,
  "branch_preferences": ["cs_it", "ece"],
  "max_results": 90,
  "lang": "en"
}
```

- `adv_rank` and `mains_rank`: At least one is required.
- `goal`: `coding` | `research` | `mba` | `core` | `undecided`.
- `data_mode`: `basic` | `extended`.
- `seat_category`: `OPEN` | `OBC-NCL` | `SC` | `ST` | `EWS` | `PwD`.
- `brand_branch_ratio`: Float between `0.0` (pure branch focus) and `1.0` (pure brand focus).
- `branch_preferences`: List of branch families to filter by (e.g. `cs_it`, `ece`, `ee`, `mechanical`, etc.).
- `lang`: `en` | `hi` | `gu` | `kn` (default is `en`).

---

## Project Structure

```
.
├── app/
│   ├── __init__.py
│   └── disha/               # Backend modules
│       ├── __init__.py
│       ├── config.py        # Env-based settings (CORS, data paths, modes)
│       ├── data_loader.py   # Excel/CSV -> Program dataclasses (cached)
│       ├── recommender.py   # Pipeline: filter -> categorise -> rank -> probability
│       ├── schemas.py       # Pydantic request/response models
│       ├── states.py        # States, quotas, branch tags, goal weights
│       └── data/
│           ├── JEE_2025_Cutoffs.xlsx
│           └── merged_jee_cutoff_2018_2025.csv
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
│   ├── test_recommender.py
│   └── test_enhancements.py
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

## Recommendation Algorithm & Pipeline

Disha implements a multi-stage, intelligent recommendation pipeline that processes student ranks, demographic quotas, and career goals to deliver ranked college and branch suggestions.

### 1. Data Ingestion & Caching
- **Basic Mode**: Loads **2,410 rows** of JoSAA 2025 OPEN (CRL) Round 6 cutoffs from the Excel sheet (`JEE_2025_Cutoffs.xlsx`).
- **Extended Mode**: Loads historical cutoffs from 2018–2025 (`merged_jee_cutoff_2018_2025.csv`) covering all reservation categories (**OBC-NCL, SC, ST, EWS, PwD, and OPEN**).
- Both datasets are parsed once at application startup, validated, and cached in-memory as Pydantic models for sub-millisecond response times.

### 2. Multi-Stage Filtering
Each program (institute-branch pair) is passed through five sequential filters:
- **Exam Match**: JEE Advanced rank is matched only to IIT programs; JEE Main rank is matched to NIT, IIIT, and GFTI programs.
- **Gender Pool**: Male candidates are restricted to `Gender-Neutral` seats. Female candidates are eligible for both `Gender-Neutral` and `Female-Only` seats.
- **Quota Match**: Filters seats by quota eligibility:
  - **All India (AI)** and **IITs** are open to all.
  - **Home State (HS)** seats are kept if the candidate's home state matches the institute's state.
  - **Other State (OS)** seats are kept if the candidate's home state is different.
  - Special state-specific quotas (e.g., Goa, Jammu & Kashmir) are mapped to their respective beneficiary states.
- **Category Match**: In Extended mode, matches the student's reservation category (e.g., SC, OBC-NCL) to the corresponding seat quota.
- **Branch Preference**: If the user selects preferred branches (e.g., CS/IT, ECE), only programs matching those branch tags are retained.

### 3. Rank Categorization & Pruning
Each program is categorized into one of three buckets based on the candidate's rank relative to last year's opening rank ($OR$) and closing rank ($CR$):
- **Safe**: The candidate's rank is better than or equal to the opening rank ($\text{Rank} \le OR$).
- **Target**: The candidate's rank lies between the opening and closing ranks ($OR < \text{Rank} \le CR$).
- **Reach**: The candidate's rank is slightly beyond the closing rank, up to a 25% upper margin ($CR < \text{Rank} \le CR \times 1.25$).
- **Overqualification Pruning**: To keep suggestions realistic and high-aiming, programs where the candidate's rank is significantly better than the opening rank ($\text{Rank} < OR \times 0.50$) are pruned.

### 4. Personalized Tag-Weight Scoring (Career Alignment)
To rank programs by the student's personal interests, branches are mapped to tags (e.g., `cs`, `it`, `circuital`, `core`). Each career goal has a pre-defined tag weight:
- **Coding**: High weights for `cs` (10) and `it` (8).
- **Research**: High weights for `physics`, `chemistry`, `math_computing` (8-10).
- **MBA / Management**: Balanced weights across circuital and core engineering.
- **Core Engineering**: High weights for `mechanical`, `civil`, `chemical`, `ee` (9-10).

The final interest score blends the **Branch Interest Score** (from the tag weights) and the **Institute Brand Score** (a normalized tier rating) using the user's **Brand-vs-Branch Ratio Slider** ($\alpha \in [0, 1]$):
$$\text{Score} = (1 - \alpha) \times \text{Branch Score} + \alpha \times (\text{Brand Score} \times 10)$$

### 5. Admission Probability & Volatility Estimation
Rather than presenting static cutoffs, Disha estimates the statistical probability of admission ($P$) using a logistic sigmoid function of the Z-score:
$$z = \frac{CR - \text{Rank}}{\sigma}$$
$$P = \frac{1}{1 + e^{-1.7 \cdot z}}$$
Where:
- $\sigma$ is the historical volatility (standard deviation of closing ranks across 2018–2025).
- If historical data is insufficient, it defaults to $8\%$ of the closing rank (with a floor of $5\%$ or $10$ ranks).
- Cutoff stability is classified into **High** ($\text{spread} \ge 6,000$ ranks), **Medium**, or **Fragile** ($\text{spread} < 1,000$ ranks or $CR \le OR$) to alert students of volatile cutoffs.

### 6. Sorting Order
The final recommendations are sorted by:
1. **Category Order**: `Target` (highest priority) $\to$ `Reach` $\to$ `Safe`.
2. **Interest Score**: Descending (aligning with the student's career goal and brand/branch preference).
3. **Closing Rank**: Ascending (harder/more competitive branches first).
4. **Institute Name**: Alphabetically.

---

## Configuration

The application is configured using environment variables (which can be specified in a `.env` file at the root):

| Env Variable | Default | Description |
|--------------|---------|-------------|
| `CORS_ORIGINS` | `*` | Comma-separated list of allowed origins (or `*` for all) |
| `DATA_PATH` | `app/disha/data/JEE_2025_Cutoffs.xlsx` | Path to the basic Excel cutoff file |
| `EXTENDED_DATA_PATH` | `app/disha/data/merged_jee_cutoff_2018_2025.csv` | Path to the extended historical CSV file |
| `DATA_MODE` | `basic` | Default data mode (`basic` or `extended`) |
| `ALLOW_USER_DATA_TOGGLE` | `True` | Allow users to toggle between basic and extended mode in the UI |

---

## Running Tests

To run the complete test suite:

```bash
# Activate your virtual environment
source .venv/bin/activate

# Run pytest
pytest tests/ -v
```

---

## Data Sources

Cutoffs are sourced from the [atmabodha/OpenNLP JEE dataset](https://github.com/atmabodha/OpenNLP) (JoSAA 2025, OPEN CRL, Round 6 closing ranks), published by UTMT. This tool is for guidance only and does not guarantee admission outcomes.

---

## License

MIT © 2026
