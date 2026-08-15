# Contributing to Disha

This file exists mainly to prevent the thing that just happened to this repo from happening again: the README and integration docs described a version of the project that no longer existed — wrong HTTP methods, wrong constants, no mention of COMEDK or KCET at all — because documentation was treated as a separate, later task instead of part of the change that made it stale.

## The rule

**Any change to backend endpoints or response/request shapes, frontend structure, setup/run steps, or the process for adding a new exam must come with a corresponding update to the docs in the same change.** Not as a follow-up PR. Not "I'll circle back to docs later." In the same commit/PR/agent session as the code change.

This applies equally to a human contributor and to an AI coding agent (Antigravity, Claude Code, or anything else) working on this repo. If you are an agent reading this file while implementing a task like **"add exam X"** or **"fix Y in the backend"**, treat a docs-update pass as an implicit, default part of that task — don't wait to be told to update docs separately.

## Docs checklist — run this before calling any change finished

- [ ] **Did I add or change an API endpoint, or a request/response field?**
  → Update [docs/API.md](docs/API.md) (the authoritative per-exam contract, including the request/response tables and the cross-exam comparison table at the bottom). If the change is significant enough to affect the quick-orientation table in the README, update that too.
- [ ] **Did I add a new exam, or change how an existing exam's backend/frontend is structured?**
  → Update the README's [Architecture overview](README.md#architecture-overview), [Directory layout](README.md#directory-layout), and [Adding a new exam](README.md#adding-a-new-exam) sections. If you changed how the *frontend* is organized specifically, also update [templates/disha_templates/README.md](templates/disha_templates/README.md).
- [ ] **Did I change setup, install, or run steps** (a new dependency, a new required env var, a new way to launch the server)?
  → Update the README's [Setup](README.md#setup) section.
- [ ] **Did I discover or fix a bug that a doc currently describes as "working" or "broken"** (e.g. the KCET `/recommend` 500, or the service worker's stale `kcet.html` path)?
  → Update the specific caveat/warning in [docs/API.md](docs/API.md) or the README's exam-status table to reflect the new reality — don't leave a "known bug" note in place once the bug is fixed, and don't leave something documented as "working" once you've broken it.
- [ ] **Did I add, remove, or rename a file under `templates/disha_templates/`?**
  → Update the directory tree in [templates/disha_templates/README.md](templates/disha_templates/README.md) and, if it changes the shared-vs-per-exam picture, the README's Architecture section too.

If none of the boxes above apply — e.g. a pure refactor with no behavior change, a typo fix, a dependency bump with no new capability — no docs update is required. Use judgment, but default to "update docs" when in doubt.

## Why this is written the way it is

Every doc file in this repo (README.md, docs/API.md, this file, templates/disha_templates/README.md) was rewritten by reading the actual code rather than trusting what the old docs claimed — including verifying, live, that `POST /api/kcet/recommend` returns a 500 and that `sw.js`'s KCET cache path doesn't exist. Docs that assert a specific verified behavior ("verified bug", "confirmed with `TestClient`") should keep being backed by an actual check, not carried forward as folklore. If you can't verify a claim against the current code before writing it down, either verify it or say explicitly that it's unconfirmed (see the KCET quota-code caveat in `docs/API.md` for the pattern) — don't guess and present the guess as fact.

## Copy-and-adapt exams: don't touch another exam's files

Per the README's [Adding a new exam](README.md#adding-a-new-exam) section: the exams' *pipelines* are still independently maintained, but registration and curation are now shared. When adding or fixing one exam, do not edit another exam's files (`app/disha/<exam>/*`, `templates/disha_templates/<exam>/*`) unless the change is specifically about that exam.

The shared files you *are* expected to edit across exams:

- `app/disha/registry.py` — one `ExamRegistration` entry per exam; router mounting and page routes are generated from it. `app/disha/routes.py` no longer needs editing.
- `templates/disha_templates/js/landing.js` — the picker card.
- `tests/golden/matrix.py` — add your exam's request matrix, or it has no safety net.

`app/disha/core/` is shared by every exam and must never import from an exam package. If you find yourself wanting to add an `if exam == "..."` there, that is the signal the abstraction is wrong — push the difference into the exam's own module instead.

**Behaviour changes must not ride along inside a refactor.** If a change alters any API response, the golden suite will fail; re-capture it in its own commit so the diff is a reviewable record of what changed.

## Tests

Run `pytest tests/ -v` before and after your change. Note that JEE is the only exam with test coverage today (`tests/test_api.py`, `tests/test_recommender.py`, `tests/test_enhancements.py`) — if you're changing COMEDK or KCET, there is no existing suite to catch a regression, so verify manually (e.g. spin up the server and hit the endpoint, or use `fastapi.testclient.TestClient` in a scratch script) before considering the change done. Adding a test file for the exam you're touching is welcome and not required by this policy, but strongly encouraged given the KCET bug this doc rewrite uncovered specifically *because* no test existed to catch it.
