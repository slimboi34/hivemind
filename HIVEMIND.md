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

## Re-engineering candidates

- **Drop the Zep Cloud dependency.** It is the one hard external service. Replace it with a
  local graph (SQLite or Kuzu) so Hivemind runs on just an LLM key.
- **Native Claude support.** It currently goes through Anthropic's OpenAI-compatible endpoint.
- **Measure whether it predicts anything.** Upstream publishes no backtests. Add a harness
  that replays past events and scores the forecasts.
- **Cost controls.** Agents × rounds × LLM calls adds up. Add per-run budgets and a cheap
  model for the crowd with a strong model for the report.
- **Slimmer install.** camel-oasis pulls in torch and sentence-transformers.
