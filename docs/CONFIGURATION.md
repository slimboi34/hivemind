# Configuration

Every setting Hivemind reads, where it is read, its default and what it changes. The list
comes from a search of the code for `os.environ`, `os.getenv`, `Config.` and
`import.meta.env`, plus `.env.example`.

## How settings are loaded

- **Backend.** `backend/app/config.py` loads the repo-root `.env` with `override=True`, so a
  value in `.env` wins over the same variable already set in the shell. If there is no root
  `.env` (for example in the Docker image, which excludes it), only real environment
  variables are used.
- **Simulation subprocess.** `backend/scripts/run_parallel_simulation.py` loads the root
  `.env` too (without override), and it inherits the Flask process's environment.
- **Frontend.** Vite reads `VITE_*` variables at build time and bakes them into the bundle.
- **Startup check.** `backend/run.py` refuses to start if `LLM_API_KEY` or `ZEP_API_KEY` is
  missing, or if `ZEP_API_URL` is set.

`.env` is gitignored. `./hivemind.sh` creates it from `.env.example` on first run.

## Contents

- [Required](#required)
- [Language model](#language-model)
- [Zep Cloud](#zep-cloud)
- [Server](#server)
- [Simulation](#simulation)
- [Cast growth](#cast-growth)
- [Public mode](#public-mode)
- [Optional integrations](#optional-integrations)
- [Frontend build](#frontend-build)
- [Set by the platform or by Hivemind itself](#set-by-the-platform-or-by-hivemind-itself)
- [Read but not used](#read-but-not-used)
- [Fixed in code](#fixed-in-code)

## Required

| Variable | Read in | Default | Effect |
| --- | --- | --- | --- |
| `LLM_API_KEY` | `config.py`, simulation scripts, `agent_spawner.py` | none | Key for the LLM provider. Every model call uses it. |
| `ZEP_API_KEY` | `config.py`, `utils/zep.py` | none | Key for Zep Cloud (knowledge graph and agent memory). |

## Language model

| Variable | Default in code | In `.env.example` | Effect |
| --- | --- | --- | --- |
| `LLM_BASE_URL` | `https://api.openai.com/v1` | `https://api.anthropic.com/v1/` | Base URL of an OpenAI-compatible Chat Completions API. |
| `LLM_MODEL_NAME` | `gpt-4o-mini` | `claude-haiku-5-5` | Model for everything: seed brief, ontology, personas, config, the crowd's actions, joiners, the report agent, chat, interviews, briefing and recap. The briefing and recap caches record which model wrote them. |
| `LLM_BOOST_API_KEY` | unset | commented out | If set, the Reddit-like platform in a parallel run uses this second endpoint, so the two platforms can spread load across providers or accounts. |
| `LLM_BOOST_BASE_URL` | unset | commented out | Base URL for the boost endpoint. |
| `LLM_BOOST_MODEL_NAME` | `LLM_MODEL_NAME` | commented out | Model for the boost endpoint. |

Notes:

- The code defaults are OpenAI's; the template sets Anthropic's. With the template, the model
  is Claude Haiku 5.5 through Anthropic's OpenAI-compatible endpoint. A larger model writes
  better and costs several times more, because every simulated participant makes a call every
  round.
- `utils/openai_chat_compat.py` adapts requests per model family: for Claude 5 and later it
  omits `temperature` and the `json_object` response format (the prompts already require
  JSON); for GPT-5 it omits `temperature` and sends `max_completion_tokens`. Other models get
  the standard request.
- When a provider explicitly rejects `response_format`, the client retries once without it.

## Zep Cloud

| Variable | Default | Effect |
| --- | --- | --- |
| `ZEP_API_KEY` | none | See [Required](#required). |
| `ZEP_API_URL` | must be unset | Rejected at startup and in `get_zep_client`. The Zep SDK would otherwise let it override the Cloud URL; Hivemind supports Zep Cloud only (`https://api.getzep.com/api/v2`). |

## Server

| Variable | Read in | Default | Effect |
| --- | --- | --- | --- |
| `FLASK_HOST` | `run.py` | `0.0.0.0` | Interface the backend binds to. `.env.example` sets `127.0.0.1` so a laptop does not expose the API to its network. The Docker image sets `0.0.0.0`. |
| `FLASK_PORT` | `run.py` | — | Backend port. Takes precedence over `PORT`. |
| `PORT` | `run.py` | — | Used when `FLASK_PORT` is unset (Railway provides it). If neither is set, 5001. |
| `FLASK_DEBUG` | `config.py` | `False` | `true` turns on Flask debug mode and the reloader, with a warning. Not for production. |
| `HIVEMIND_STATIC_DIR` | `app/__init__.py` | unset | If it points at a folder containing `index.html`, Flask serves the built frontend from it on the same port as the API. The Docker image sets `/app/frontend/dist`. |

## Simulation

| Variable | Read in | Default | Effect |
| --- | --- | --- | --- |
| `HIVEMIND_REPORT_MAX_INTERVIEWS` | `config.py`, `report_agent.py` | `4` | Most simulated people the report agent interviews in one batch (each answers on both platforms). |
| `HIVEMIND_INTERVIEW_TIMEOUT_SECONDS` | `config.py`, `zep_tools.py` | `420` | How long the report agent waits for a batch of interviews. Under API rate limits a batch of 6 took about 3.5 minutes. |
| `HIVEMIND_MEMORY_WAIT_SECONDS` | `config.py`, `simulation_runner.py` | `120` | After the last round, how long to wait for Zep to process the run's memories before a report may start anyway. Every batch must have been delivered first. |
| `OASIS_DEFAULT_MAX_ROUNDS` | `config.py`, `api/simulation.py`, `public_mode.py` | `10` | Round cap applied when a start request sets no `max_rounds`. `0` removes the cap. In public mode it is a ceiling for every request, and `/api/public/status` reports it as `max_rounds`. |
| `HIVEMIND_EMBED_BATCH` | `scripts/oasis_patches.py` | `32` | How many texts the Twitter recommender's twhin-bert model embeds per forward pass. Lower uses less memory; the embeddings are identical either way. Minimum 1. |
| `HIVEMIND_ENV_LIFETIME_MINUTES` | `scripts/run_parallel_simulation.py` | unset (keep alive until closed) | After the last round, close the kept-alive agents after this many minutes. `0` or unset keeps them until `close-env`, a stop or a restart. The Docker image sets `20`. |
| `HF_HOME` | Hugging Face libraries (via OASIS) | the library default | Where the twhin-bert model is cached. The Docker image sets `/app/backend/uploads/.hf`, on the volume, so it is downloaded once. |

## Cast growth

Read by `services/cast_growth.py::settings()`, which is used both in the Flask process (the
circle, at setup) and in the subprocess (joiners, during the run). Precedence, lowest first:
the defaults, then `growth_config` in the run's `simulation_config.json` (not written by
setup; only if you add it by hand), then these environment variables.

| Variable | Default | Effect |
| --- | --- | --- |
| `HIVEMIND_CIRCLE` | on | Add the people around key actors at setup. `0`, `false`, `no` or `off` turns it off; anything else turns it on. |
| `HIVEMIND_CIRCLE_ANCHORS` | `6` | How many of the most-connected actors get a circle. |
| `HIVEMIND_CIRCLE_PER_ANCHOR` | `2` | Accounts added around each anchor. |
| `HIVEMIND_JOIN` | on | Let accounts join while the run is under way. Same boolean rule. |
| `HIVEMIND_JOIN_FIRST_ROUND` | `2` | First round at which newcomers may join. |
| `HIVEMIND_JOIN_EVERY` | `2` | Look for newcomers every N rounds (minimum 1). |
| `HIVEMIND_JOIN_PER_WAVE` | `3` | Most newcomers in one look. |
| `HIVEMIND_JOIN_MAX` | `12` | Most newcomers in the whole run. |

Numbers must be non-negative integers; invalid values are ignored. Whatever the settings, the
circle and the joiners are each capped at a quarter of the evidence cast (never fewer than 2),
because invented accounts should not outnumber the people the evidence names.

## Public mode

Read by `backend/app/public_mode.py`. Full policy in [DEPLOYMENT.md](./DEPLOYMENT.md).

| Variable | Default | Effect |
| --- | --- | --- |
| `HIVEMIND_PUBLIC` | off | `1`, `true` or `yes` turns on the public-site guard, lowers the upload limit to 20 MB and records usage in `uploads/public_quota.json`. The Docker image sets `1`. |
| `HIVEMIND_RUNS_PER_DAY` | `5` | New runs per UTC day, shared by all visitors. |
| `HIVEMIND_RUNS_PER_VISITOR` | `1` | New runs per visitor (IP) per UTC day. |
| `HIVEMIND_CHATS_PER_VISITOR` | `20` | Chat messages and interviews per visitor per UTC day. A batch interview costs one per person asked. |
| `HIVEMIND_CHATS_PER_DAY` | `150` | Chat messages and interviews per UTC day in total. |
| `HIVEMIND_ADMIN_TOKEN` | unset | Enables `GET /api/admin/headers` and `POST /api/admin/import` for requests whose `X-Admin-Token` header matches. Unset means both return 404. |
| `HIVEMIND_SOURCE_ARCHIVE` | unset | Path of the source archive served at `/source.tar.gz`. The Docker image builds `/opt/hivemind-source.tar.gz` and points here. |

Invalid integers fall back to the default.

## Optional integrations

| Variable | Default | Effect |
| --- | --- | --- |
| `GODSEYE_URL` | `http://localhost:4173` | Where Hivemind looks for a local God's Eye View server for the live-data seed connector. No key needed. The connector is disabled on the public site. |

## Frontend build

Read by Vite at build time (`import.meta.env`).

| Variable | Default | Effect |
| --- | --- | --- |
| `VITE_API_BASE_URL` | `http://localhost:5001` | Base URL the app calls for the API (`frontend/src/api/index.js`, PDF downloads). The Docker image builds with `/` so calls go to the same origin. |
| `VITE_PUBLIC` | unset | `1` builds the public-site variant: the home page shows how many free runs are left today and that runs are public, the header links to `/source.tar.gz` ("Source") instead of GitHub, the God's Eye importer is hidden, and the briefing and recap Rewrite buttons are hidden. |

The dev server's port (3000) and its `/api` proxy to `localhost:5001` are set in
`frontend/vite.config.js`. The app calls the backend directly through
`VITE_API_BASE_URL`, with CORS open on `/api/*`.

## Set by the platform or by Hivemind itself

You do not normally set these.

| Variable | Set by | Purpose |
| --- | --- | --- |
| `PORT` | Railway | The port to listen on. |
| `RAILWAY_DOCKERFILE_PATH` | you, as a Railway service variable | Tells Railway to build `deploy/Dockerfile`. Not read by the app. See [DEPLOYMENT.md](./DEPLOYMENT.md#railway-setup). |
| `OPENAI_API_KEY`, `OPENAI_API_BASE_URL` | the simulation scripts, from `LLM_API_KEY` / `LLM_BASE_URL` (or the boost values) | CAMEL reads its OpenAI-compatible settings from these. `agent_spawner.py` falls back to them. |
| `PYTHONUTF8=1`, `PYTHONIOENCODING=utf-8` | `simulation_runner.py`, for the subprocess | Make OASIS read files as UTF-8 on every platform. |
| `WERKZEUG_RUN_MAIN` | Werkzeug's reloader | Used to log startup and register shutdown cleanup only once in debug mode. |
| `UV_LINK_MODE`, `UV_COMPILE_BYTECODE`, `PYTHONUNBUFFERED` | `deploy/Dockerfile` | Build and logging behaviour inside the image. |

## Read but not used

These are read into `Config` but nothing uses them today. Changing them has no effect.

| Variable | Default | Note |
| --- | --- | --- |
| `REPORT_AGENT_MAX_TOOL_CALLS` | `5` | The report agent uses its own constants: 3 to 5 tool calls per section, 2 per chat. |
| `REPORT_AGENT_MAX_REFLECTION_ROUNDS` | `2` | Not used. |
| `REPORT_AGENT_TEMPERATURE` | `0.5` | The report agent uses 0.5 for sections and chat and 0.3 for the outline, hard-coded. |
| `SECRET_KEY` | `hivemind-secret-key` | Hivemind uses no sessions or signed cookies. |

## Fixed in code

Values that are constants, not settings. Change them in the code if you need to.

| What | Value | Where |
| --- | --- | --- |
| Upload size limit | 50 MB (20 MB in public mode) | `Config.MAX_CONTENT_LENGTH`, `public_mode.register` |
| Upload types | `pdf`, `md`, `markdown`, `txt` | `Config.ALLOWED_EXTENSIONS` |
| Default chunking | 500 characters, 50 overlap (overridable per build request) | `Config.DEFAULT_CHUNK_SIZE`, `DEFAULT_CHUNK_OVERLAP` |
| Evidence sent to the ontology step | 50,000 characters, sampled from up to 60 chunks of 8,000 | `OntologyGenerator` |
| Ontology size | 10 entity types, 10 relationship types, 10 attributes | `utils/ontology.py` |
| Zep request timeout, ingestion wait | 60 s, 600 s | `utils/zep.py` |
| Zep search limits | query 400 characters, 50 results | `utils/zep.py` |
| Zep read retries | 3 attempts, exponential backoff, honours `Retry-After` | `utils/zep.py` |
| Personas written at once | 5 (sent by the UI) | `Step2EnvSetup.vue`, `/prepare` |
| Agents per config batch | 15 | `SimulationConfigGenerator.AGENTS_PER_BATCH` |
| Concurrent model requests per platform | 30 | `oasis.make(..., semaphore=30)` |
| Monitor poll, IPC poll | 2 s, 0.5 s | `simulation_runner.py`, `simulation_ipc.py`, subprocess |
| Graph-memory batch | 5 actions per platform, 0.5 s apart, episodes under 9,500 characters | `ZepGraphMemoryUpdater` |
| Report sections, tool calls | 2–5 sections; 3–5 tool calls and up to 5 replies per section | `report_agent.py` |
| Interview timeouts | 60 s single, 120 s batch, 180 s all | `api/simulation.py` |
| Analytics refresh | every 5 s while a run is live | `AnalyticsView.vue` |
| Public write-ups per run | 3 per write-up | `public_mode._WRITES_PER_RUN` |
| Quota history kept | 7 days of daily counters | `public_mode._save` |
