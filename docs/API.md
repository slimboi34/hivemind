# HTTP API reference

Every endpoint the Flask app registers, grouped by blueprint. Paths, methods, parameters and
response shapes are taken from `backend/app/__init__.py`, `backend/app/public_mode.py` and
`backend/app/api/*.py`.

## Conventions

- **Base URL.** Locally `http://localhost:5001`. On the public site the API and the app share
  one origin, so paths are relative (`/api/...`).
- **Envelope.** JSON responses look like `{"success": true, "data": {...}}` or
  `{"success": false, "error": "message"}`. List endpoints usually add `"count"`. Many 500
  responses also include a `"traceback"` field with the Python stack trace when run locally;
  the public site strips it before the response leaves the server.
- **Language.** The frontend sends `Accept-Language` with the UI locale. If it matches a
  translation file (`en` or `zh`), backend messages and LLM output use that language;
  otherwise English.
- **Long jobs.** Graph build, simulation prepare and report generation return a `task_id` at
  once. Poll the matching status endpoint. Task records are kept in memory; the status
  endpoints fall back to files on disk after a restart.
- **CORS** is open (`*`) on `/api/*`.
- **IDs.** Projects `proj_<12 hex>`, simulations `sim_<12 hex>`, reports `report_<12 hex>`,
  Zep graphs `hivemind_<16 hex>`, tasks are UUIDs.

### Public mode column

With `HIVEMIND_PUBLIC=1` (the public site), a guard runs before every `/api/` request. The
**Public** column says what it does:

| Value | Meaning |
| --- | --- |
| open | Allowed, no limit. |
| new run | Counts as a new run: at most `HIVEMIND_RUNS_PER_DAY` (5) per UTC day site-wide and `HIVEMIND_RUNS_PER_VISITOR` (1) per visitor; refused (429) while a simulation is running. |
| own run, once | Only for a project or simulation started on this site, and only once. Earlier runs get 403 "Earlier runs are read-only". |
| metered | Counts against the chat budget: `HIVEMIND_CHATS_PER_VISITOR` (20) per visitor and `HIVEMIND_CHATS_PER_DAY` (150) in total, per UTC day. 429 when used up. |
| refused | 403 "This action is turned off on the public site." (or "Deleting is turned off…" for every `DELETE`). |

In addition, on the public site any `POST` whose JSON body has `"force": true` or
`"force_regenerate": true` is refused with 403, except `POST /api/simulation/start`. Denials
carry `"public_limit": true`. See [DEPLOYMENT.md](./DEPLOYMENT.md#public-mode-policy) for the
full policy.

## Contents

- [Service endpoints](#service-endpoints)
- [Graph: /api/graph](#graph-apigraph)
- [Simulation: /api/simulation](#simulation-apisimulation)
  - [Entities](#entities)
  - [Create and prepare](#create-and-prepare)
  - [Run control and status](#run-control-and-status)
  - [Run data](#run-data)
  - [Analytics and write-ups](#analytics-and-write-ups)
  - [Interviews and the live environment](#interviews-and-the-live-environment)
- [Report: /api/report](#report-apireport)
- [God's Eye View: /api/godseye](#gods-eye-view-apigodseye)

## Service endpoints

Registered in `app/__init__.py` and `public_mode.register`.

| Method | Path | Purpose | Public |
| --- | --- | --- | --- |
| GET | `/health` | Liveness check. Returns `{"status": "ok", "service": "Hivemind Backend"}`. Railway's health check uses it. | open |
| GET | `/api/public/status` | Public-site limits. Without public mode: `{"public": false}`. With it: `public`, `runs_today`, `runs_per_day`, `runs_left_today`, `visitor_runs_left_today`, `busy` (a simulation is running), `max_rounds`, and `visitor` (first 8 hex characters of a SHA-256 of the visitor's IP, for checking that visitors are told apart). | open |
| GET | `/source.tar.gz` | The source the running image was built from (AGPL-3.0 section 13). Served from `HIVEMIND_SOURCE_ARCHIVE`; 404 if not built in. | open |
| GET | `/api/admin/headers` | Owner only (`X-Admin-Token` header must equal `HIVEMIND_ADMIN_TOKEN`). Shows the forwarding headers the edge sends and the IP `client_ip()` would use. Returns 404 without a valid token. | token |
| POST | `/api/admin/quota/reset` | Owner only. Gives today's runs and chats back to everyone (for example after the owner's own test run) by clearing today's counters in `public_quota.json`. Returns `{"cleared": {"runs": n, "chats": n}}`. Which runs were started on the site is kept. | token |
| POST | `/api/admin/import` | Owner only. Multipart field `archive`: a `.tar.gz` whose members start with `projects/`, `simulations/` or `reports/`. Other members are ignored; extraction uses tarfile's `data` filter. Clears the cached run states. Returns `{"imported": <member count>}`. | token |
| GET | `/` and `/<path>` | Only when `HIVEMIND_STATIC_DIR` contains `index.html`: serves the built app. Existing files are served directly (`assets/` cached for a year); anything else returns `index.html` so client-side routes work. Unknown `/api/...` paths return 404. | open |

## Graph: /api/graph

`backend/app/api/graph.py`.

| Method | Path | Purpose | Public |
| --- | --- | --- | --- |
| POST | `/api/graph/ontology/generate` | Start a run: save the evidence, write a brief if there is none, design the ontology. | new run |
| POST | `/api/graph/build` | Build the Zep knowledge graph for a project (background task). | own run, once |
| GET | `/api/graph/task/<task_id>` | Status of a background task. | open |
| GET | `/api/graph/tasks` | All tasks in memory. | open |
| GET | `/api/graph/data/<graph_id>` | Nodes and edges of a graph. | open |
| GET | `/api/graph/project/<project_id>` | One project record. | open |
| GET | `/api/graph/project/list` | Projects, newest first. | open |
| POST | `/api/graph/project/<project_id>/reset` | Delete the project's Zep graph and return it to `ontology_generated`. | refused |
| DELETE | `/api/graph/project/<project_id>` | Delete the project's Zep graph and its folder. | refused |
| DELETE | `/api/graph/delete/<graph_id>` | Delete a Zep graph and clear the reference from every project that uses it. | refused |

### POST /api/graph/ontology/generate

`multipart/form-data`:

| Field | Required | Meaning |
| --- | --- | --- |
| `simulation_requirement` | yes | The question to simulate. |
| `files` | no, repeatable | PDF, Markdown or text files (`pdf`, `md`, `markdown`, `txt`). Max request size 50 MB (20 MB on the public site). |
| `seed_text` | no | Pasted evidence. Saved as `pasted-notes.txt`. |
| `project_name` | no | Defaults to `Unnamed Project`. |
| `additional_context` | no | Extra instructions for the ontology step. |

Response `data`: `project_id`, `project_name`, `ontology` (`entity_types`, `edge_types`),
`analysis_summary`, `files` (`filename`, `size`), `total_text_length`, `seed_source`
(`documents`, `pasted` or `brief`).

Errors: 400 if the question is missing or files were sent but none could be read. 502 if
the model returned unusable JSON or the provider failed (the message includes the HTTP
status and request id, never the provider's body). 500 otherwise. On failure after the
project was created, `data.project_id` is included and the project is marked `failed`.

### POST /api/graph/build

JSON body:

| Field | Default | Meaning |
| --- | --- | --- |
| `project_id` | required | From the ontology step. |
| `graph_name` | project name | Name for the Zep graph. |
| `chunk_size` | 500 | Characters per chunk. Positive integer, at most 10,000 in practice (Zep's item limit). |
| `chunk_overlap` | 50 | Must satisfy `0 <= overlap < chunk_size`. |
| `force` | `false` | Rebuild a completed or failed graph (deletes the old one). |

Response `data`: `project_id`, `task_id`, `resumed` (an interrupted Zep batch was picked up),
`message`. If the graph is already complete (and not forced) or a build is in progress, the
existing `task_id` and `graph_id` are returned with `reused: true`. 409 if a build was
interrupted and cannot be resumed (`recoverable: true`), or if the graph is in use.

The task's `result` on completion: `project_id`, `graph_id`, `node_count`, `edge_count`,
`chunk_count`, `zep_batch_id`.

### GET /api/graph/task/&lt;task_id&gt;

`data`: `task_id`, `task_type`, `status` (`pending`, `processing`, `completed`, `failed`),
`created_at`, `updated_at`, `progress` (0–100), `message`, `progress_detail`, `result`,
`error`, `metadata`. 404 if unknown.

### GET /api/graph/data/&lt;graph_id&gt;

`data`: `graph_id`, `node_count`, `edge_count`, `nodes[]` (`uuid`, `name`, `labels`,
`summary`, `attributes`, `created_at`), `edges[]` (`uuid`, `name`, `fact`, `fact_type`,
`source_node_uuid`, `target_node_uuid`, `source_node_name`, `target_node_name`, `attributes`,
`created_at`, `valid_at`, `invalid_at`, `expired_at`, `episodes`).

### GET /api/graph/project/list

Query: `limit` (default 50). `data` is a list of project records (fields in
[ARCHITECTURE.md](./ARCHITECTURE.md#what-is-stored-on-disk)).

## Simulation: /api/simulation

`backend/app/api/simulation.py`.

### Entities

Read the typed entities from a graph. These call Zep each time.

| Method | Path | Purpose | Public |
| --- | --- | --- | --- |
| GET | `/api/simulation/entities/<graph_id>` | Entities whose label is one of the ontology's types. Query: `entity_types` (comma-separated filter), `enrich` (`true` by default: include edges and neighbours). | open |
| GET | `/api/simulation/entities/<graph_id>/<entity_uuid>` | One entity with its context. 404 if missing. | open |
| GET | `/api/simulation/entities/<graph_id>/by-type/<entity_type>` | Entities of one type. Query: `enrich`. Returns `entity_type`, `count`, `entities`. | open |

### Create and prepare

| Method | Path | Purpose | Public |
| --- | --- | --- | --- |
| POST | `/api/simulation/create` | Create a simulation for a project's graph. | own run, once (one simulation per project) |
| POST | `/api/simulation/prepare` | Read the cast, write personas, generate the config (background task). | own run; an earlier run that is already prepared gets its stored setup back |
| POST | `/api/simulation/prepare/status` | Progress of setup. | open |
| POST | `/api/simulation/generate-profiles` | Generate profiles straight from a graph without creating a simulation (debugging). | refused |
| GET | `/api/simulation/<simulation_id>` | The simulation record. When `ready`, includes `run_instructions` (commands to run the scripts by hand). | open |
| GET | `/api/simulation/list` | All simulations. Query: `project_id`. | open |
| GET | `/api/simulation/history` | Simulations with project details for the home page history. Query: `limit` (default 20). | open |
| GET | `/api/simulation/<simulation_id>/profiles` | Agent profiles. Query: `platform` (`reddit` or `twitter`; default is the simulation's default platform, `reddit` when both are on). | open |
| GET | `/api/simulation/<simulation_id>/profiles/realtime` | Profiles read straight from disk while they are being written, with `count`, `total_expected`, `is_generating`, `file_exists`, `file_modified_at`. | open |
| GET | `/api/simulation/<simulation_id>/config` | The generated `simulation_config.json`. 404 until it exists. | open |
| GET | `/api/simulation/<simulation_id>/config/realtime` | The config as it is being written, with `is_generating` and `generation_stage`. | open |
| GET | `/api/simulation/<simulation_id>/config/download` | `simulation_config.json` as a file. | open |
| GET | `/api/simulation/script/<script_name>/download` | One of `run_twitter_simulation.py`, `run_reddit_simulation.py`, `run_parallel_simulation.py`, `action_logger.py`. | refused |

**POST /api/simulation/create** body: `project_id` (required), `graph_id` (defaults to the
project's), `enable_twitter` (default `true`), `enable_reddit` (default `true`). Returns the
simulation record: `simulation_id`, `project_id`, `graph_id`, `enable_twitter`,
`enable_reddit`, `status: created`, counts, flags, timestamps.

**POST /api/simulation/prepare** body:

| Field | Default | Meaning |
| --- | --- | --- |
| `simulation_id` | required | |
| `entity_types` | all | Only cast entities of these types. |
| `use_llm_for_profiles` | `true` | `false` writes rule-based profiles without the LLM. |
| `parallel_profile_count` | 5 | Personas written at once. |
| `force_regenerate` | `false` | Redo setup even if it is complete. |

Response `data` when work starts: `simulation_id`, `task_id`, `status: preparing`,
`already_prepared: false`, `expected_entities_count`, `entity_types`. When the run is already
prepared: `status: ready`, `already_prepared: true`, `prepare_info` (`status`,
`entities_count`, `profiles_count`, `entity_types`, `config_generated`, `existing_files`,
timestamps).

**POST /api/simulation/prepare/status** body: `task_id` and/or `simulation_id`. If the
simulation is already prepared, returns `status: ready`, `progress: 100`,
`already_prepared: true`. Otherwise the task record, whose `progress_detail` has
`current_stage` (`reading`, `generating_profiles`, `generating_config`, `copying_scripts`),
`stage_index`, `total_stages`, `stage_progress`, `current_item`, `total_items`,
`item_description`.

### Run control and status

| Method | Path | Purpose | Public |
| --- | --- | --- | --- |
| POST | `/api/simulation/start` | Start the simulation subprocess. | own run, once; refused (429) while another simulation runs; rounds clamped |
| POST | `/api/simulation/stop` | Kill the subprocess (process group). | refused |
| GET | `/api/simulation/<simulation_id>/run-status` | Live run state. | open |
| GET | `/api/simulation/<simulation_id>/run-status/detail` | Run state plus every action. Query: `platform`. | open |

**POST /api/simulation/start** body:

| Field | Default | Meaning |
| --- | --- | --- |
| `simulation_id` | required | |
| `platform` | `parallel` | `twitter`, `reddit` or `parallel`. The UI always sends `parallel`. |
| `max_rounds` | `OASIS_DEFAULT_MAX_ROUNDS` (10) | Cap on rounds. Positive integer. On the public site, `min(max_rounds, 10)`. |
| `enable_graph_memory_update` | `false` | Write agent activity back into the Zep graph. The UI sends `true`. Requires the project's current graph; refused (409) while a report is reading that graph. |
| `force` | `false` | Stop a previous run of this simulation, delete its logs (`run_state.json`, `actions.jsonl`, `simulation.log`, `env_status.json` and the databases; never the config or profiles) and start again. The UI sends `true`. |

Response `data`: the run state (below) plus `max_rounds_applied`,
`graph_memory_update_enabled`, `force_restarted`, and `graph_id` when memory is on. 400 if
the simulation is not prepared or is already running without `force`. 409 if a previous run
cannot be finalised safely or the graph changed.

**POST /api/simulation/stop** body: `simulation_id`. Returns the final run state. 202 with
`pending: true` if graph-memory ingestion is still draining.

**Run state** (`run-status`), as stored in `run_state.json`: `simulation_id`,
`runner_status` (`idle`, `starting`, `running`, `paused`, `stopping`, `stopped`,
`completed`, `failed`), `current_round`, `total_rounds`, `progress_percent`,
`simulated_hours`, `total_simulation_hours`, `twitter_current_round`,
`reddit_current_round`, `twitter_simulated_hours`, `reddit_simulated_hours`,
`twitter_running`, `reddit_running`, `twitter_completed`, `reddit_completed`,
`ready_for_report`, `twitter_actions_count`, `reddit_actions_count`, `total_actions_count`,
`started_at`, `updated_at`, `completed_at`, `error`, `process_pid`. Before a run starts it
returns `runner_status: idle` with zero counts.

`ready_for_report: true` while `runner_status` is still `running` means every round has
finished and the agents are being kept alive for interviews.

**run-status/detail** adds `all_actions`, `twitter_actions`, `reddit_actions`,
`recent_actions` (the current round only) and `rounds_count`. Each action:
`round_num`, `timestamp`, `platform`, `agent_id`, `agent_name`, `action_type`,
`action_args`, `result`, `success`.

### Run data

| Method | Path | Purpose | Public |
| --- | --- | --- | --- |
| GET | `/api/simulation/<simulation_id>/actions` | Actions, newest first. Query: `limit` (100), `offset` (0), `platform`, `agent_id`, `round_num`. Returns `count`, `actions`. | open |
| GET | `/api/simulation/<simulation_id>/timeline` | Per-round summary. Query: `start_round` (0), `end_round`. Each round: `round_num`, `twitter_actions`, `reddit_actions`, `total_actions`, `active_agents_count`, `active_agents`, `action_types`, `first_action_time`, `last_action_time`. | open |
| GET | `/api/simulation/<simulation_id>/agent-stats` | Per-agent action counts by platform and type. Returns `agents_count`, `stats`. | open |
| GET | `/api/simulation/<simulation_id>/posts` | Rows from the platform's SQLite `post` table, newest first. Query: `platform`, `limit` (50), `offset`. Returns `platform`, `total`, `count`, `posts`. | open |
| GET | `/api/simulation/<simulation_id>/comments` | Rows from the `comment` table. Query: `platform`, `post_id`, `limit` (50), `offset`. | open |

### Analytics and write-ups

All read-only over a run's files except the two `POST`s, which call the LLM once and cache the
result. Every field is explained in [ANALYTICS.md](./ANALYTICS.md).

| Method | Path | Purpose | Public |
| --- | --- | --- | --- |
| GET | `/api/simulation/<simulation_id>/analytics` | Activity per round, interaction network, rankings, top posts, action mix. Adds `simulation_id` and `run` (`status`, `current_round`, `total_rounds`). | open |
| GET | `/api/simulation/<simulation_id>/dynamics` | Run health checks, cascade trees, engagement consensus. | open |
| GET | `/api/simulation/<simulation_id>/cast` | The cast as a tree (group → kind → person → the people around them), with setup progress and who joined. | open |
| GET | `/api/simulation/<simulation_id>/recap` | "What happened": facts plus the cached AI story if it matches the current data, otherwise a template story. | open |
| POST | `/api/simulation/<simulation_id>/recap` | Have the LLM write the story and cache it. Body: `force` (rewrite even if cached). 502 if the model call fails. | finished runs only (409 before), at most 3 writes per run, `force` refused |
| GET | `/api/simulation/<simulation_id>/briefing` | The briefing: facts, confidence, and the cached AI reading or a template reading. | open |
| POST | `/api/simulation/<simulation_id>/briefing` | Have the LLM write the reading and cache it. Body: `force`. 502 if the model call fails. | finished runs only (409 before), at most 3 writes per run, `force` refused |
| GET | `/api/simulation/<simulation_id>/consensus-report.pdf` | The briefing PDF, `<simulation_id>-hivemind-briefing.pdf`. Query: `write=1` writes the AI briefing and story first if the run has finished and they are not cached. | open |

### Interviews and the live environment

These need the run's environment to be alive (after the last round, until it is closed or
its lifetime runs out). Otherwise they return 400 "environment not running".

| Method | Path | Purpose | Public |
| --- | --- | --- | --- |
| POST | `/api/simulation/interview` | Interview one agent. | metered (1) |
| POST | `/api/simulation/interview/batch` | Interview several agents in one command. The Interaction page uses this for single interviews and surveys. | metered (1 per interview in the list) |
| POST | `/api/simulation/interview/all` | Ask every agent the same question. | refused |
| POST | `/api/simulation/interview/history` | Past interviews from the SQLite `trace` table. Body: `simulation_id`, `platform`, `agent_id`, `limit` (100). Returns `count`, `history[]` (`agent_id`, `response`, `prompt`, `timestamp`, `platform`). | open |
| POST | `/api/simulation/env-status` | Body: `simulation_id`. Returns `env_alive`, `twitter_available`, `reddit_available`, `message`. | open |
| POST | `/api/simulation/close-env` | Ask the environment to close gracefully. Body: `simulation_id`, `timeout` (30). Marks the simulation `completed`. | refused |

**POST /api/simulation/interview** body: `simulation_id`, `agent_id`, `prompt` (all
required), `platform` (`twitter` or `reddit`; omit to ask on both), `timeout` (60 s). Before
sending, the backend prefixes the prompt with an instruction to answer from the persona and
the agent's memories in plain text, without calling tools. With one platform the result is
`{agent_id, response, platform, timestamp}`; with both it is
`{agent_id, prompt, platforms: {twitter: {...}, reddit: {...}}}`. 504 on timeout.

**POST /api/simulation/interview/batch** body: `simulation_id`, `interviews` (list of
`{agent_id, prompt, platform?}`), `platform` (default for items without one), `timeout`
(120 s). `data.result.results` is keyed `twitter_<agent_id>` / `reddit_<agent_id>`.

**POST /api/simulation/interview/all** body: `simulation_id`, `prompt`, `platform`,
`timeout` (180 s).

## Report: /api/report

`backend/app/api/report.py`.

| Method | Path | Purpose | Public |
| --- | --- | --- | --- |
| POST | `/api/report/generate` | Start the report agent (background task). | returns the existing report if there is one (free, not counted); otherwise once per simulation, including earlier runs without a report; `force_regenerate` refused |
| POST | `/api/report/generate/status` | Progress of generation. Body: `task_id` and/or `simulation_id`. If a completed report exists for the simulation, returns `status: completed`, `already_completed: true`. | open |
| GET | `/api/report/<report_id>` | The report. | open |
| GET | `/api/report/by-simulation/<simulation_id>` | Latest report for a simulation. 404 with `has_report: false` if none. | open |
| GET | `/api/report/list` | Reports. Query: `simulation_id`, `limit` (50). | open |
| GET | `/api/report/<report_id>/download` | `full_report.md` as `<report_id>.md`. | open |
| DELETE | `/api/report/<report_id>` | Delete a report folder. | refused |
| POST | `/api/report/chat` | Chat with the report agent. | metered (1) |
| GET | `/api/report/<report_id>/progress` | `status`, `progress`, `message`, `current_section`, `completed_sections`, `updated_at`. | open |
| GET | `/api/report/<report_id>/sections` | Sections written so far: `sections[]` (`filename`, `section_index`, `content`), `total_sections`, `is_complete`. | open |
| GET | `/api/report/<report_id>/section/<section_index>` | One section's Markdown. | open |
| GET | `/api/report/check/<simulation_id>` | `has_report`, `report_status`, `report_id`, `interview_unlocked` (a completed report exists). | open |
| GET | `/api/report/<report_id>/agent-log` | Structured agent log from line `from_line` (0): `logs[]`, `total_lines`, `from_line`, `has_more`. Each entry has `timestamp`, `elapsed_seconds`, `action`, `stage`, `section_title`, `section_index`, `details`. | open |
| GET | `/api/report/<report_id>/agent-log/stream` | The whole agent log at once. | open |
| GET | `/api/report/<report_id>/console-log` | Plain-text console lines from `from_line`. | open |
| GET | `/api/report/<report_id>/console-log/stream` | The whole console log at once. | open |
| POST | `/api/report/tools/search` | Debug: one graph search. Body: `graph_id`, `query`, `limit` (10). | refused |
| POST | `/api/report/tools/statistics` | Debug: graph statistics. Body: `graph_id`. | refused |

**POST /api/report/generate** body: `simulation_id` (required), `force_regenerate`
(default `false`). Response `data`: `simulation_id`, `report_id`, `task_id`,
`status: generating`, `already_generated: false`; or, when a completed report exists and
regeneration was not forced, `report_id`, `status: completed`, `already_generated: true`.

Refused with 409 when the run or its graph-memory ingestion is still active, when the run did
not finish successfully, when the project's graph is not complete, or when the simulation was
prepared against an older graph.

**Report record** (`GET /api/report/<id>`): `report_id`, `simulation_id`, `graph_id`,
`simulation_requirement`, `status` (`pending`, `planning`, `generating`, `completed`,
`failed`), `outline` (`title`, `summary`, `sections[]` with `title`, `content`),
`markdown_content`, `created_at`, `completed_at`, `error`.

**POST /api/report/chat** body: `simulation_id`, `message` (required), `chat_history`
(list of `{role, content}`; the last 10 are used). Response `data`: `response`,
`tool_calls` (the tool calls made), `sources` (their queries).

## God's Eye View: /api/godseye

`backend/app/api/godseye.py`. An optional connector to a God's Eye View server running
locally (`GODSEYE_URL`, default `http://localhost:4173`). It calls neither the LLM nor Zep.

| Method | Path | Purpose | Public |
| --- | --- | --- | --- |
| GET | `/api/godseye/status` | Whether God's Eye View answers (10 s timeout), its version and the tools Hivemind may use, plus the available `sections`. | refused |
| POST | `/api/godseye/brief` | Build a Markdown situation brief for an area. | refused |

**POST /api/godseye/brief** body: `area` (required) and `sections` (any of `headlines`,
`hazards`, `weather`, `air`, `sea`). `area` is a place name, or an object with `place`, or
`lat` and `lon` (with optional `radius_km`, default 100, at most 2,000), or a `bbox` of four
numbers. Returns the brief and a suggested `filename`. 404 if the place cannot be resolved,
503 if God's Eye View is unreachable, 502 if it fails.

Only aggregate data is used. Tools that identify or track one person, aircraft or vessel, and
camera or licence-plate tools, are refused inside the client.
