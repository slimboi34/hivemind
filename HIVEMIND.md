# Hivemind

Our working copy of **MiroFish** (official repo: https://github.com/666ghj/MiroFish,
mirofish.ai), a swarm-intelligence "predict anything" engine. Step 1 is running it
unchanged; step 2 is re-engineering it into Hivemind.

- Git remote `upstream` = the official MiroFish repo. Pull its updates with
  `git fetch upstream && git merge upstream/main`.
- License: **AGPL-3.0**. Anything we build from this code stays AGPL. If we ever run it
  as a public web service, we must offer users the source.

## Run it

1. Put your keys in `.env` (gitignored): `LLM_API_KEY` and `ZEP_API_KEY`.
2. `./hivemind.sh` starts frontend http://localhost:3000 and backend http://127.0.0.1:5001.

Node 22 comes from nvm (Vite 7 needs Node 20.19 or newer). Python 3.12 venv is in `backend/.venv` (uv).

## How it works (5 stages)

1. **Graph building**: upload seed docs (pdf/md/txt). The LLM designs an ontology, then the
   text goes into a **Zep Cloud** knowledge graph (`backend/app/services/graph_builder.py`).
2. **Environment setup**: entities in the graph become agent personas with configs
   (`oasis_profile_generator.py`, `simulation_config_generator.py`).
3. **Simulation**: CAMEL-AI **OASIS** runs the agents on a simulated Twitter and Reddit in
   parallel, as subprocesses (`backend/scripts/run_*_simulation.py`). Agent actions are
   written back into Zep as memory.
4. **Report**: a ReportAgent with tools queries the graph and the simulation results (`report_agent.py`).
5. **Interaction**: chat with any simulated agent or with the ReportAgent.

Stack: Flask API (`backend/app/api/{graph,simulation,report}.py`, about 20k lines of Python)
and a Vue 3 + Vite frontend (`frontend/`).

## What Hivemind adds

Rule: new features read the outputs MiroFish already produces and never change the
prediction pipeline (ontology, personas, OASIS run, report agent), so forecasts stay
identical to upstream.

- **English by default.** UI, LLM output and backend messages default to `en`; the language
  switcher still offers the other locales.
- **Simulation Analytics** (`/simulation/<id>/analytics`, "Analytics" button in Step 3).
  Backed by `GET /api/simulation/<id>/analytics` (`backend/app/services/simulation_analytics.py`),
  a read-only aggregation of `{twitter,reddit}/actions.jsonl`:
  - influence network: who engaged with whom (support / oppose / reply), node size =
    engagement received, node colour = support share, round-by-round replay
  - activity per round stacked by kind, with a table view
  - top influencers (engagement, reach, support share) and a per-agent drill-down
  - most-engaged posts and the action-type mix
  - updates every 5 s while a simulation is running; `?agent=Name` deep-links a selection
- **Run dynamics & consensus PDF** (same Analytics page).
  Backed by `GET /api/simulation/<id>/dynamics` and
  `GET /api/simulation/<id>/consensus-report.pdf`
  (`trace_reader.py`, `run_dynamics.py`, `consensus_report.py`):
  - cascade trees from the sqlite `trace` table (branching, orphans, structural virality)
  - run health card (blind activations, participation, feed concentration, horizon)
  - engagement consensus plain-language verdict
  - these diagnostics are the appendix of the briefing PDF
- **Briefing** (top of the Analytics page, and the first pages of the PDF).
  `GET/POST /api/simulation/<id>/briefing` (`run_briefing.py`): what a run means.
  - Facts are deterministic. Each simulated participant is placed in a reader-friendly group
    (companies and executives, government and regulators, investors and analysts, media,
    experts, public voices) by keyword-matching the entity type the run already gave them.
    Each group gets counts, how warmly its posts were received, who backed whom, and verbatim posts.
  - The LLM interprets only those facts: the bottom line, where groups agree, where they split,
    how each group reacted and its likely next step, each company's position and likely move,
    and what to watch. A template fills the same shape with no LLM.
  - A deterministic "how far to trust this" level (Solid / Directional / Thin) comes from the
    run-health checks and participation.
  - Cached in `uploads/simulations/<id>/briefing.json`, keyed to the facts. Written once per
    finished run when Analytics is opened or the PDF is downloaded.
- **Briefing PDF** (`consensus_report.py`, **Download briefing PDF** on Analytics).
  Order: bottom line, consensus, splits, group reactions, company reactions, what to watch,
  the story of the run, then run diagnostics as an appendix. `?write=1` has the backend write
  the AI reading and story first if they are missing.
- **Start from a question alone** (`seed_brief.py`, home screen).
  Evidence is optional. `POST /api/graph/ontology/generate` accepts uploaded files, pasted text
  (`seed_text`), both, or neither. With neither, the LLM writes a background brief (situation,
  named stakeholders by group, relationships, timeline, open questions) that becomes the seed
  document. This does change the input to the prediction pipeline for those runs: the brief
  comes from the model's general knowledge and can be out of date, and it says so at the top.
  Runs that upload documents are unaffected.
- **What happened** (Analytics page, and the story section of the PDF).
  `GET/POST /api/simulation/<id>/recap` (`run_recap.py`): a plain-language story of each run.
  - Facts are deterministic. Rounds are grouped into stretches (one per round for short runs,
    four stretches for longer ones, one per simulated day for multi-day runs). Each stretch
    records posts, replies, approving/disapproving reactions, new voices, the standout post
    (quoted verbatim) and pushback.
  - The LLM narrates only from those facts. A template writes the same shape with no LLM,
    shown while a run is live or if the model call fails.
  - Once a run finishes, opening Analytics writes the story automatically. It is cached in
    `uploads/simulations/<id>/recap.json` and keyed to the action log, so it is written
    once per run. "Rewrite" forces a new one.

## Re-engineering candidates

- **Drop the Zep Cloud dependency.** It is the one hard external service. Replace it with a
  local graph (SQLite or Kuzu) so Hivemind runs on just an LLM key.
- **Native Claude support.** It currently goes through Anthropic's OpenAI-compatible endpoint.
- **Measure whether it predicts anything.** Upstream publishes no backtests. Add a harness
  that replays past events and scores the forecasts.
- **Cost controls.** Agents × rounds × LLM calls adds up. Add per-run budgets and a cheap
  model for the crowd with a strong model for the report.
- **Slimmer install.** camel-oasis pulls in torch and sentence-transformers.
