# Hivemind

Maintainer notes. The public documentation starts at [README.md](README.md) and lives in
[docs/](docs/); this file keeps the working notes short and points there for detail.

**What it is:** a social swarm simulation tool. It builds a fake internet around a situation:
it researches the topic, deploys a swarm of AI agents as the people and organisations
involved, runs them on simulated social platforms, and reports how they react.

- License: **AGPL-3.0**. Part of this code derives from an AGPL project, so everything built
  from it stays AGPL, the LICENSE file and the short notice in the README must stay, and as a
  public web service it must offer users the source (it does, at `/source.tar.gz`).

## Run it

1. Put your keys in `.env` (gitignored): `LLM_API_KEY` and `ZEP_API_KEY`.
2. `./hivemind.sh` starts the frontend on http://localhost:3000 and the backend on
   http://127.0.0.1:5001.
3. Tests: `cd backend && uv run pytest` (offline, about 270 tests). CI runs them and the
   frontend build on every push (`.github/workflows/tests.yml`).

Node 22 comes from nvm (Vite 7 needs Node 20.19 or newer). The Python 3.12 venv is
`backend/.venv` (uv). Details: [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).

## How it works (5 stages)

1. **Graph building**: seed docs (pdf/md/txt), pasted text, or a brief the LLM writes from the
   question alone. The LLM designs an ontology, then the text goes into a **Zep Cloud**
   knowledge graph (`backend/app/services/graph_builder.py`).
2. **Environment setup**: entities in the graph become agent personas with configs
   (`oasis_profile_generator.py`, `simulation_config_generator.py`), plus the circle around key
   actors (`cast_circle.py`).
3. **Simulation**: CAMEL-AI **OASIS** runs the agents on a simulated Twitter and Reddit in
   parallel, as a subprocess (`backend/scripts/run_parallel_simulation.py`). Agent actions are
   written back into Zep as memory. After the last round the process stays alive for interviews.
4. **Report**: a ReportAgent with tools queries the graph and interviews agents (`report_agent.py`).
5. **Interaction**: chat with the ReportAgent or interview and survey the simulated agents.

Stack: Flask API (`backend/app/api/{graph,simulation,report,godseye}.py`; about 31k lines of
Python including the simulation scripts) and a Vue 3 + Vite frontend (`frontend/`). Full
walk-through: [docs/PIPELINE.md](docs/PIPELINE.md); process model:
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## What Hivemind adds

Rule: measurement features read the outputs a run already produces and never change the
prediction pipeline (ontology, personas, OASIS run, report agent). Changes to that pipeline
are listed separately below and say so.

**Measurement and write-ups** (read-only; definitions in [docs/ANALYTICS.md](docs/ANALYTICS.md)):

- **English by default.** UI, LLM output and backend messages default to `en`; the language
  switcher offers every locale with a strings file (English and Chinese today).
- **Simulation Analytics** (`/simulation/<id>/analytics`, "Analytics" button in Step 3).
  `GET /api/simulation/<id>/analytics` (`simulation_analytics.py`), a read-only aggregation of
  `{twitter,reddit}/actions.jsonl`: influence network (support / oppose / reply, node size =
  engagement received, fill = support share, ring = group, round-by-round replay), activity per
  round, top influencers, per-agent drill-down, most-engaged posts, action mix. Updates every
  5 s while a run is live; `?agent=Name` deep-links a selection.
- **Run dynamics** (`GET /api/simulation/<id>/dynamics`; `trace_reader.py`, `run_dynamics.py`):
  cascade trees from the sqlite `trace` table (branching, orphans, structural virality), the
  run health card (feed visibility, participation, action mix, feed concentration, branching,
  horizon) and an engagement-consensus verdict.
- **What happened** (`GET/POST /api/simulation/<id>/recap`, `run_recap.py`): deterministic
  chapters of facts, narrated by the LLM from those facts only, with a template fallback.
  Cached in `recap.json`, keyed to the action log.
- **Briefing** (`GET/POST /api/simulation/<id>/briefing`, `run_briefing.py`): participants
  grouped by keyword-matching their entity type; the LLM interprets only those facts (bottom
  line, consensus, splits, group and company reactions, what to watch); a deterministic
  confidence level (Solid / Directional / Thin) from the health checks and participation.
  Cached in `briefing.json`, keyed to the facts. Written once per finished run when Analytics
  is opened or the PDF is downloaded.
- **Briefing PDF** (`consensus_report.py`, `GET /api/simulation/<id>/consensus-report.pdf`):
  bottom line, consensus, splits, group and company reactions, what to watch, the story, run
  diagnostics, and an excerpt of the long-form report. `?write=1` writes missing AI text first.
- **Cast tree** (`GET /api/simulation/<id>/cast`, `run_cast.py`, `CastTree.vue`): run → group →
  kind → participant → the people around them. `cast_progress.json` lets agents light up as
  their personas are written.
- **Graph view**: nodes sized by how connected they are, hover fades everything more than one
  step away, labels not cut short.

**Changes to the simulation** (these do affect a run's output):

- **Start from a question alone** (`seed_brief.py`). With no evidence, the LLM writes a
  background brief that becomes the seed document. It comes from the model's general knowledge,
  can be out of date, and says so at the top. Runs with documents are unaffected.
- **Agent casting fixes** (see [docs/research/AGENT_ARCHITECTURE.md](docs/research/AGENT_ARCHITECTURE.md),
  section 3): people-typed entities are written as people, not institutions, and each opening
  post goes to the account that would really post it.
- **Round cap**: `OASIS_DEFAULT_MAX_ROUNDS` (10) applies when no round count is given; on the
  public site it is a ceiling.
- **Busy-hour start**: the simulated clock starts at the first hour when half the cast is
  awake, instead of midnight.
- **Cast growth** (`cast_growth.py`, `cast_circle.py`, `scripts/agent_spawner.py`): the circle
  (people around the 6 most connected actors, 2 each) at setup, and newcomers who join every 2
  rounds from round 2 when a thread draws them in. Named by role, labelled by origin, each kind
  capped at a quarter of the evidence cast. `HIVEMIND_CIRCLE=0` / `HIVEMIND_JOIN=0` turn them off.
- **OASIS runtime patches** (`scripts/oasis_patches.py`): the quote-post feed crash (17–46% of
  Twitter-side turns were blind in stored runs), `[feed-error]` logging, and batched
  twhin-bert embeddings (`HIVEMIND_EMBED_BATCH`, default 32; same vectors, far less memory).
- **Kept-alive agents and early reports**: when every platform has logged `simulation_end`,
  graph memory is drained and the run is marked `ready_for_report` while the process stays
  alive for interviews. `HIVEMIND_ENV_LIFETIME_MINUTES` closes it after a while (20 on the
  public site).

## Public site (Railway)

Live at https://hivemind-production-25f13fa5.up.railway.app (Railway project `hivemind`,
service `hivemind`, volume `hivemind-volume` at `/app/backend/uploads`). It runs on the
owner's Anthropic and Zep keys, so `HIVEMIND_PUBLIC=1` turns on spend and safety limits
(`backend/app/public_mode.py`). Full detail: [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

- New runs: `HIVEMIND_RUNS_PER_DAY` (5) shared by everyone, `HIVEMIND_RUNS_PER_VISITOR` (1)
  per visitor IP per UTC day, none while a simulation is running (a finished run's kept-alive
  agents count as running). Rounds are capped at `OASIS_DEFAULT_MAX_ROUNDS` (10) whatever the
  caller asks for; Step 2 shows the cap instead of a round picker.
- Each paid step (graph build, simulation create/prepare/start, report) works once, and only
  on runs started on the site. Earlier runs are read-only; opening an earlier run's setup page
  returns its stored setup without model calls. A report can be generated once for an earlier
  run that has none.
- Briefing and "What happened" are written by the LLM once a run has finished (at most 3
  writes per run each); forced rewrites are refused and the Rewrite buttons are hidden.
- Chat with agents or the report agent: `HIVEMIND_CHATS_PER_VISITOR` (20) per visitor and
  `HIVEMIND_CHATS_PER_DAY` (150) in total. A batch interview costs one per person asked.
- Off on the public site: deletes, resets, stop/close, `generate-profiles`, `interview/all`,
  forced regeneration (except the run page's own start), the God's Eye View connector, report
  tool endpoints, script downloads.
- Finished runs keep their agents alive for `HIVEMIND_ENV_LIFETIME_MINUTES` (20), then close;
  the Interaction page then says the agents are offline and points to the report agent.
- Usage is kept in `uploads/public_quota.json`; `GET /api/public/status` shows what is left.
- Visitors are told apart by `X-Real-IP`. Railway's edge overwrites it and `X-Forwarded-For`
  (whose last entry is the shared edge node, not the visitor). Checked 2026-11-19 with spoofed
  headers; `GET /api/admin/headers` re-checks it.
- AGPL: `/source.tar.gz` serves the source the image was built from; the header links to it.
- The home page says runs are public. Everyone's runs appear in the history list.

Build: `deploy/Dockerfile` (selected by the service variable
`RAILWAY_DOCKERFILE_PATH=deploy/Dockerfile`, because Railway ignored `dockerfilePath` in
`railway.json`; the root `Dockerfile` is the local dev image). It builds the frontend with
`VITE_PUBLIC=1` and `VITE_API_BASE_URL=/`, installs CPU-only torch (the lockfile's Linux torch
pulls ~3 GB of CUDA), and Flask serves `frontend/dist`. The twhin-bert model cache lives on the
volume (`HF_HOME`). `railway.json` (health check, restart policy) is deprecated config-as-code
after 2026-12-01; move those settings into the service before then.

Deploy: `railway up --detach -s hivemind` from the repo root (it honours `.gitignore`, so
`.env`, local runs and `linkedin/` stay local). Keys are service variables, never files.

Admin (header `X-Admin-Token`, the `HIVEMIND_ADMIN_TOKEN` service variable; a copy is in
`~/.config/hivemind/railway.env`):

- `POST /api/admin/import`: copy earlier local runs up (a tar.gz of `projects/`,
  `simulations/`, `reports/`, field `archive`). Everything imported becomes public.
- `POST /api/admin/quota/reset`: give today's runs and chats back after a test run.
- `GET /api/admin/headers`: see the forwarding headers the edge sends.

## Re-engineering candidates

The full review of how agents are created and how the system is put together, with a ranked
plan, is in [docs/research/AGENT_ARCHITECTURE.md](docs/research/AGENT_ARCHITECTURE.md). How
information spreads between agents is in
[docs/research/INFORMATION_DYNAMICS.md](docs/research/INFORMATION_DYNAMICS.md). Both are
dated snapshots: some of their items have since been built (the health card, cascade metrics,
the feed-crash fix, cast growth). Known limits are listed in
[docs/LIMITATIONS.md](docs/LIMITATIONS.md).

- **Drop the Zep Cloud dependency.** It is the one hard external service. Replace it with a
  local graph (SQLite or Kuzu) so Hivemind runs on just an LLM key.
- **Native Claude support.** It currently goes through Anthropic's OpenAI-compatible endpoint
  (with a compatibility layer for Claude 5's request rules).
- **Measure whether it predicts anything.** There are no backtests. Add a harness that replays
  past events and scores the forecasts.
- **Make runs repeatable and the feeds sound.** Seed the randomness per run, fix the
  recommender's randomly initialised pooler, and use the hot order on the Reddit side
  (INFORMATION_DYNAMICS, section on fixes).
- **Cost controls.** The round cap is in. Still to do: per-run budgets, and a cheap model for
  the crowd with a strong model for the report.
- **Production serving.** Werkzeug's dev server in one process holds tasks, locks and running
  simulations in memory. A real deployment needs a WSGI server and that state moved out of
  process.
- **Finish the translation.** Runtime strings are in English now. The ontology, persona and
  simulation-config prompts, and many code comments, are still written in Chinese.
- **Slimmer install.** camel-oasis pulls in torch and sentence-transformers.
