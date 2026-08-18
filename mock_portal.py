"""
Mock UTMT portal — pretends to be Sir's main.py.
Mounts Disha's router under /learning_games, exactly like they will.
DELETE THIS FILE before handing the repo to Sir — it's test-only.
"""
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.disha.routes import router as disha_router

app = FastAPI(title="Mock UTMT Portal")

# Order matters — router BEFORE static mount, same as Body Quest's main.py
app.include_router(disha_router, prefix="/learning_games", tags=["learning_games"])

DISHA_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates" / "disha_templates"
app.mount(
    "/learning_games",
    StaticFiles(directory=str(DISHA_TEMPLATES_DIR), html=True),
    name="disha",
)

@app.get("/")
def portal_home():
    return {"portal": "mock utmt", "hint": "try /learning_games/"}