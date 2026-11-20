# Development guide

How to run Hivemind on your machine, run the tests, find your way around the code, translate
the interface, and add a feature in the house style.

## Contents

- [Prerequisites](#prerequisites)
- [Run it](#run-it)
- [Tests](#tests)
- [Code tour](#code-tour)
- [Frontend routes](#frontend-routes)
- [Localisation](#localisation)
- [Adding a feature](#adding-a-feature)
- [Conventions](#conventions)
- [Logs and debugging](#logs-and-debugging)
- [Inherited code](#inherited-code)

## Prerequisites

| Tool | Version | Why |
| --- | --- | --- |
| Node.js | 20.19 or newer; 22 recommended (`.nvmrc` says 22) | Vite 7 needs at least 20.19 |
| Python | 3.11 or 3.12 (`requires-python = ">=3.11,<3.13"`); 3.12 is what the image uses | backend and OASIS |
| [uv](https://docs.astral.sh/uv/) | any recent | installs the locked Python environment in `backend/.venv` |
| An LLM key | | `LLM_API_KEY`, for example from [console.anthropic.com](https://console.anthropic.com/) |
| A Zep Cloud key | | `ZEP_API_KEY` from [app.getzep.com](https://app.getzep.com/); the free tier covers small runs |

The first simulation downloads `Twitter/twhin-bert-base` from Hugging Face for the
recommender. The Python dependencies include PyTorch, so the first `uv sync` is large.

## Run it

```bash
git clone https://github.com/slimboi34/hivemind.git
cd hivemind
./hivemind.sh
```

What `hivemind.sh` does, in order:

1. Puts the newest Node 22 from nvm (`~/.nvm/versions/node/v22.*`) first on the `PATH`, if
   there is one.
2. Creates `.env` from `.env.example` if it does not exist.
3. Stops with instructions if `LLM_API_KEY` or `ZEP_API_KEY` is empty or still a placeholder.
4. Runs `npm run setup` if `node_modules` or `frontend/node_modules` is missing, and
   `uv sync` in `backend/` if `backend/.venv` is missing.
5. Runs `npm run dev`, which starts both servers with `concurrently`.

| Server | URL | Command |
| --- | --- | --- |
| Frontend (Vite, opens a browser) | http://localhost:3000 | `npm run frontend` (`vite --host`) |
| Backend (Flask) | http://localhost:5001 | `npm run backend` (`cd backend && uv run python run.py`) |

Other scripts in the root `package.json`:

| Script | Does |
| --- | --- |
| `npm run setup` | `npm install` at the root and in `frontend/` |
| `npm run setup:backend` | `uv sync` in `backend/` |
| `npm run setup:all` | both |
| `npm run build` | production build of the frontend into `frontend/dist` |

The frontend calls the API at `VITE_API_BASE_URL` (default `http://localhost:5001`) with CORS.
Vite also proxies `/api` to port 5001.

To try the single-container production setup locally, build the app with
`VITE_API_BASE_URL=/`, then start the backend with `HIVEMIND_STATIC_DIR=frontend/dist`
(absolute path) and open http://localhost:5001. Add `HIVEMIND_PUBLIC=1` to try public mode.

**A cheap first run.** Type a question and press Run simulation; no documents are needed. On
the setup screen, leave the rounds on auto: with no limit sent, the backend's default cap of 10
rounds applies. When it finishes, open Analytics and download the briefing PDF.

## Tests

```bash
cd backend
uv run pytest
```

`uv sync` installs `pytest` and `pytest-asyncio` from the `dev` dependency group. The suite has
about 270 tests in 32 files and runs offline: LLM and Zep calls are replaced with fakes, and
analytics tests build action lists by hand with a small `act()` helper. Run one file with
`uv run pytest tests/test_run_briefing.py -q`.

| Area | Test files |
| --- | --- |
| Ontology and seed | `test_ontology_generator.py`, `test_ontology_attributes.py`, `test_ontology_api_errors.py`, `test_seed_brief.py` |
| LLM client | `test_llm_json_responses.py`, `test_openai_chat_compat.py` |
| Cast and personas | `test_agent_casting.py`, `test_cast_growth.py`, `test_platform_profiles.py`, `test_profile_field_normalization.py`, `test_run_cast.py` |
| Simulation lifecycle | `test_simulation_prepare_failure.py`, `test_simulation_round_cap.py`, `test_simulation_ready_for_report.py`, `test_oasis_patches.py` |
| Zep integration contracts | `test_zep_cloud_contracts.py`, `test_zep_edge_paging.py`, `test_zep_entity_reader_edges.py`, `test_zep_graph_lifecycle.py`, `test_zep_graph_memory_updater.py`, `test_zep_report_barrier.py`, `test_zep_retry_and_client.py`, `test_zep_simulation_barrier.py`, `test_zep_cloud_validation_script.py` |
| Report agent | `test_report_tool_result_sanitizer.py` |
| Analytics and write-ups | `test_simulation_analytics.py`, `test_run_dynamics.py`, `test_run_recap.py`, `test_run_briefing.py` |
| Public mode | `test_public_mode.py` |
| God's Eye connector | `test_godseye_connector.py` |

Two manual checks live in `backend/scripts/`:

- `validate_zep_cloud_integration.py` runs a real end-to-end check against Zep Cloud. It needs
  `ZEP_API_KEY`, never prints it, and deletes its test graph unless `--keep-graph` is given.
- `test_profile_format.py` checks that generated profiles match the CSV and JSON formats OASIS
  expects.

There are no frontend unit tests; `npm run build` is the frontend's compile check.

**Continuous integration.** `.github/workflows/tests.yml` runs on every push and pull request:
the backend job installs the locked dependencies with CPU-only torch (the same way as
`deploy/Dockerfile`) and runs `pytest -q` with no API keys (tests that need live services skip
themselves); the frontend job runs `npm ci` and `npm run build` on Node 22.

## Code tour

```
hivemind/
├── hivemind.sh                    local launcher
├── package.json                   root scripts (dev, backend, frontend, build, setup)
├── .env.example                   configuration template
├── backend/
│   ├── run.py                     entry point: validate config, start Flask
│   ├── pyproject.toml, uv.lock    Python dependencies (pinned camel-oasis 0.2.5, camel-ai 0.2.78, zep-cloud 3.25.0)
│   ├── app/
│   │   ├── __init__.py            app factory: CORS, blueprints, /health, public mode, static app
│   │   ├── config.py              settings from .env
│   │   ├── public_mode.py         public-site guard, quota, source archive, admin import
│   │   ├── api/                   HTTP layer: graph.py, simulation.py, report.py, godseye.py
│   │   ├── models/                project.py (on disk), task.py (in memory)
│   │   ├── services/              the work (see below)
│   │   └── utils/                 llm_client, openai_chat_compat, zep, zep_paging, zep_lifecycle,
│   │                              retry, file_parser, ontology, locale, logger
│   ├── scripts/                   the OASIS subprocess and its helpers
│   ├── tests/                     pytest suite
│   └── uploads/                   run data (gitignored)
├── frontend/
│   ├── index.html, vite.config.js
│   └── src/
│       ├── main.js, App.vue, router/, i18n/
│       ├── api/                   axios wrappers: index.js (client), graph.js, simulation.js, report.js, godseye.js
│       ├── views/                 one per route
│       ├── components/            the five steps, the graph panel, history, header
│       │   └── analytics/         Analytics page components
│       ├── store/pendingUpload.js hands the Home form to the Process page
│       └── styles/hivemind.css    design tokens and shared styles (see docs/BRAND.md)
├── locales/                       en.json, zh.json, languages.json
├── deploy/Dockerfile              public-site image
├── Dockerfile, docker-compose.yml local development image
├── railway.json                   Railway health check and restart policy
├── brand/                         logo, mark, icon, brand board
└── docs/                          this documentation, BRAND.md, research/, images/
```

**Backend services** (`backend/app/services/`):

| File | Role |
| --- | --- |
| `seed_brief.py` | Background brief for question-only runs |
| `ontology_generator.py` | Ontology design and validation |
| `text_processor.py` | Text clean-up and chunking |
| `graph_builder.py` | Zep graph create, ontology, batch ingest, wait, read back, delete |
| `zep_entity_reader.py` | Read and filter typed entities with their edges |
| `oasis_profile_generator.py` | One persona per entity, saved in both OASIS formats |
| `simulation_config_generator.py` | Clock, opening posts, per-agent activity |
| `cast_growth.py` | Rules, prompts and validation for added accounts (no app imports, so the subprocess can load it by path) |
| `cast_circle.py` | The circle at setup |
| `simulation_manager.py` | Create and prepare simulations |
| `simulation_runner.py` | Start, stop, monitor, read actions, interviews |
| `simulation_ipc.py` | File-based command and response channel |
| `zep_graph_memory_updater.py` | Agent activity back into the graph |
| `zep_tools.py` | Search and interview tools for the report agent |
| `report_agent.py` | Outline, ReAct sections, chat; report files and logs |
| `simulation_analytics.py` | Activity analytics |
| `trace_reader.py` | Cascade trees and blind turns from SQLite |
| `run_dynamics.py` | Health checks and engagement consensus |
| `run_cast.py` | Cast tree |
| `run_recap.py` | "What happened" |
| `run_briefing.py` | The briefing |
| `consensus_report.py` | The briefing PDF |
| `godseye_client.py`, `godseye_seed.py` | God's Eye View connector |

**Simulation scripts** (`backend/scripts/`):

| File | Role |
| --- | --- |
| `run_parallel_simulation.py` | Both platforms, the round loop, logging, the wait-for-commands loop. The one the UI uses. |
| `run_twitter_simulation.py`, `run_reddit_simulation.py` | Single-platform variants (no cast growth, busy-hour start or lifetime cap) |
| `action_logger.py` | Writes `actions.jsonl` and round events |
| `oasis_patches.py` | Runtime fixes to OASIS |
| `agent_spawner.py` | Mid-run joiners and circle follows |

## Frontend routes

`frontend/src/router/index.js`:

| Path | View | Shows |
| --- | --- | --- |
| `/` | `Home.vue` | Question, evidence (upload, paste, God's Eye locally), history |
| `/process/:projectId` | `MainView.vue` | Step 1: ontology and graph build (`projectId` is `new` while the first request is in flight) |
| `/simulation/:simulationId` | `SimulationView.vue` | Step 2: setup, with the cast tree and round choice |
| `/simulation/:simulationId/start` | `SimulationRunView.vue` | Step 3: the live run (`?start=1` starts it; otherwise the page reattaches to an existing run) |
| `/simulation/:simulationId/analytics` | `AnalyticsView.vue` | Analytics, briefing, recap, PDF |
| `/report/:reportId` | `ReportView.vue` | Step 4: the report as it is written, with the agent's log |
| `/interaction/:reportId` | `InteractionView.vue` | Step 5: chat, interviews, surveys |

Every step view puts `GraphPanel.vue` (the D3 knowledge graph) beside the step component.
The `Process` route (`/process/:projectId`) is served by `views/MainView.vue`.

## Localisation

UI strings live in `locales/`, shared by both halves:

- `en.json` and `zh.json` hold the strings, in sections (`common`, `nav`, `home`, `main`,
  `step1` … `step5`, `graph`, `history`, `api`, `progress`, `log`, `report`, `console`,
  `analytics`, `godseye`, `meta`).
- `languages.json` registers languages with a `label` and an `llmInstruction` (the sentence
  appended to prompts, such as "Please respond in English."). It lists seven languages, but
  only those with a strings file are offered: today English and Chinese.

**Frontend.** `src/i18n/index.js` loads every `locales/*.json` that is also in the registry.
The chosen locale is stored in `localStorage.locale` (default `en`) and sent with every API
request as `Accept-Language`.

**Backend.** `utils/locale.py` reads `Accept-Language` (an exact match with a strings file,
else `en`). `t('section.key', name=value)` looks up a string, falls back to English and then to
the key, and fills `{name}` placeholders. `get_language_instruction()` returns the language's
`llmInstruction`; every prompt ends with it, so model output follows the UI language. Background
threads copy the request's locale with `get_locale()` / `set_locale()`.

**Adding a language:** copy `en.json` to `<code>.json`, translate the values (keep the keys
and placeholders), and make sure `languages.json` has an entry for the code. Nothing else
changes.

## Adding a feature

A worked example: a new measurement on the Analytics page.

1. **Write a pure function** in `backend/app/services/`. Take the run's actions (and, if
   needed, the config), return a dict. No disk or network access inside it, so it is easy to
   test. `build_recap_facts` and `build_briefing_facts` are models to follow.
2. **Add a read-only endpoint** in `backend/app/api/simulation.py` that loads the inputs (for
   actions, `SimulationRunner.get_all_actions(simulation_id)`), calls the function and returns
   `{"success": true, "data": ...}`.
3. **Test it** in `backend/tests/` with hand-built actions.
4. **Wire the frontend:** a wrapper in `frontend/src/api/simulation.js`, a component in
   `frontend/src/components/analytics/`, placed in `views/AnalyticsView.vue`, with strings in
   `locales/en.json` (and `zh.json`).
5. **If it calls a model or Zep**, decide its public-mode rule in `backend/app/public_mode.py`
   and test it in `tests/test_public_mode.py`. Anything that spends money on the public site
   needs a limit.
6. **Document it** in [API.md](./API.md) and [ANALYTICS.md](./ANALYTICS.md).

For a feature that does call a model, follow the briefing's pattern: compute the facts in
code, give the model only the facts, validate its JSON, fill gaps from a template, and cache
the result keyed to the inputs.

## Conventions

- **Measurement is read-only.** Code that measures a run must not change the simulation, the
  graph or the report agent's inputs.
- **Facts first, then prose.** Numbers and quotes are computed; the model only interprets
  them and is told not to invent anything. Every model-written piece has a no-model fallback.
- **Atomic writes** for any file another thread or process may read: write `*.tmp`, then
  `os.replace`.
- **Zep reads** go through `call_zep_read_with_retry`. **Zep writes** are never retried blindly;
  give them a deterministic identity and reconcile instead.
- **LLM calls** go through `LLMClient` (or `create_chat_completion`), never the raw SDK, so
  provider quirks are handled in one place. Use `chat_json` for structured output and append
  `get_language_instruction()` to prompts.
- **Background threads** capture the request's locale before starting.
- **Changes to inherited code** carry a `# Hivemind:` comment saying what changed and why.
- **Plain language** in everything a user reads. In the write-ups the platforms are "Info
  Plaza" and "Topic Community", never Twitter or Reddit, and words like "cascade", "agent" and
  "engagement" are avoided.
- **Design**: colours, type and voice follow [BRAND.md](./BRAND.md); tokens are in
  `frontend/src/styles/hivemind.css`.
- **Secrets** stay in `.env` (gitignored) locally and in service variables in production.

## Logs and debugging

| Where | What |
| --- | --- |
| Terminal and `backend/logs/YYYY-MM-DD.log` | the Flask app's log (rotating, 10 MB × 5 files) |
| `backend/uploads/simulations/<id>/simulation.log` | everything the simulation subprocess printed |
| `…/<id>/twitter/actions.jsonl`, `…/reddit/actions.jsonl` | every action, one JSON per line |
| `…/<id>/twitter_simulation.db`, `…/reddit_simulation.db` | OASIS's own tables; `trace` has every step, including feed refreshes |
| `backend/uploads/reports/<id>/agent_log.jsonl`, `console_log.txt` | the report agent's steps and tool calls |
| `backend/log/`, `backend/scripts/log/` | OASIS's own logs (gitignored) |

Useful markers in `simulation.log`: `[oasis-patch]` (which runtime fixes applied),
`[cast-growth]` (who joined and why, or why nobody did), `[feed-error]` (an agent got no feed).

## Inherited code

Hivemind derives from an open-source project released under the AGPL-3.0, and much of the
backend's structure comes from it. Runtime strings (errors, progress messages, tool results,
the report agent's prompts, the interview prefix and graph-memory episodes) have been
translated into English. Still in Chinese: many code comments, and the ontology, persona and
simulation-config prompts. Every prompt ends with a language instruction, so what users see is
in the UI language, English by default. New code, comments and prompts are written in English.

Where a translated string is parsed elsewhere, both forms are accepted so older runs still
render: the report page's tool-result parsers accept the old Chinese headings, and the interview
endpoint knows the old Chinese prefix so it never adds a prefix twice.
