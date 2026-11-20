# Limitations: what the output means and what it does not

Hivemind is a simulation tool. This page sets out, plainly, what a run can and cannot tell you,
and the known weaknesses of the engine, the measurements and the deployment. Most of these are
measured, not guessed; the evidence is in [research/INFORMATION_DYNAMICS.md](./research/INFORMATION_DYNAMICS.md)
and [research/AGENT_ARCHITECTURE.md](./research/AGENT_ARCHITECTURE.md).

## Contents

- [What a run is](#what-a-run-is)
- [Who is in the simulation](#who-is-in-the-simulation)
- [How the simulation behaves](#how-the-simulation-behaves)
- [What the numbers measure](#what-the-numbers-measure)
- [The written outputs](#the-written-outputs)
- [Language](#language)
- [The public site and the infrastructure](#the-public-site-and-the-infrastructure)
- [People, privacy and responsibility](#people-privacy-and-responsibility)

## What a run is

- **A simulation of opinion, not a prediction of outcomes.** A run shows how a cast of
  language-model personas, given a situation, posts and reacts on two simulated platforms. It
  is a rehearsal. It is not a forecast of what real people will do, not a record of real
  events, and not financial, legal or investment advice.
- **Nothing has been backtested.** No harness has yet replayed past events and scored
  Hivemind's output against what really happened. There is no measured accuracy.
- **Short horizon.** Rounds are capped at 10 by default and always on the public site. With
  the usual 60 simulated minutes per round, a run covers about 10 simulated hours: the first
  wave of reaction, not how a story develops over days or weeks. The model-designed schedule
  often asks for 72 to 168 rounds; running those locally costs proportionally more.
- **Runs are not repeatable.** Who acts each round, what each feed shows and what each model
  writes are all random, and nothing is seeded. Two runs of the same setup differ. Without
  several runs, a result cannot be separated from noise.

## Who is in the simulation

- **The cast is whoever the knowledge graph names.** Every entity Zep extracts from the
  evidence (and types with the ontology) becomes one agent, typically 25 to 80. People the
  evidence does not mention do not take part unless Hivemind adds them.
- **Added voices are invented.** The circle (people around key actors) and mid-run joiners
  are written by the model, named by role, and capped at a quarter of the evidence cast each.
  They represent kinds of people, not real individuals, and the briefing says how much of the
  writing they did.
- **One account per organisation or group.** "Shareholders" or "the public" can end up as a
  single account. The run does not model crowds, populations or proportions.
- **Personas are model-written.** Each agent's persona is the model's reading of the graph's
  facts about that entity. It inherits the model's knowledge, gaps and biases, and its
  cut-off date.
- **Question-only runs start from the model's own knowledge.** With no evidence, the
  background brief comes from what the model already knows. It can be out of date or wrong
  about recent events; the brief and the UI say so. Upload documents for anything recent or
  private.

## How the simulation behaves

These come from the CAMEL-AI OASIS engine and how Hivemind configures it.

- **Spread is mostly recommender-driven, one hop deep.** Agents start with no follows (apart
  from added accounts following the actor they surround), so on the Twitter-like platform nearly all exposure comes from a similarity recommender that shows
  each active agent 2 posts per refresh. On the Reddit-like platform a few posts are drawn at
  random from a pool of up to 100 ranked by a hot score. In the example run studied in
  `docs/research/`, every repost or quote chain was one level deep and the branching factor
  was 0.26. Information travels as broadcasts picked by the recommender, rarely as chains of
  people passing things on.
- **The recommender's similarity is partly random.** The Twitter-side recommender embeds posts
  with `Twitter/twhin-bert-base` loaded through `AutoModel` and uses its pooler output. The
  pooler weights are not part of that checkpoint, so they are randomly initialised in every
  run. Which posts count as "similar", and so who sees what, varies from run to run for that
  reason alone.
- **Feeds were often empty before the fix.** An OASIS bug made a feed fail whenever a quote
  post came first; 17 to 46 percent of Twitter-side turns in stored runs saw no feed. Hivemind
  patches this at runtime, logs any remaining feed failure, and reports the blind share in the
  run health check.
- **Few configured traits drive behaviour.** Setup writes a stance, sentiment bias, influence
  weight, posting rates and response delays for every agent, but the runner only uses
  `activity_level` and `active_hours` (with the per-hour activity range and the peak and
  off-peak multipliers). What an agent says comes from its persona and what it sees.
- **Beliefs are not modelled.** An agent's view exists only as its persona text and its growing
  conversation history. There is no opinion state that updates as it reads.
- **Simulated time is approximate.** The platforms stamp posts with their own clocks, which do
  not exactly match the simulated hour; time-based ranking depends partly on how long model
  calls take. See the research note for details.

## What the numbers measure

- **Reactions, not opinions.** "Support" counts likes, reposts, quotes, comment likes and
  follows; "oppose" counts dislikes and mutes. A quote that argues against a post still counts
  as support for its author. Support share, reception, approval and the engagement consensus
  measure how warmly the simulated accounts treated each other's posts. They are not polls of
  opinion on the question. No stance classifier reads what was written.
- **Small samples.** A 10-round run with a few dozen agents logs a few hundred actions. One
  extra reaction can move a percentage by several points. Read the run health badge and the
  briefing's confidence label (Solid, Directional, Thin) before its bottom line.
- **Health checks have known blind spots.** The blind-turn count cannot see a round in which
  every refresh failed. The branching and participation thresholds are judgement calls, set so
  that only clear faults go red.
- **Groups are keyword matches.** The briefing's groups come from matching words in each
  agent's entity type. An unusual type name can land in the wrong group or in "Other voices".

## The written outputs

- **The model interprets; it can still be wrong.** The briefing and the story are written from
  computed facts with strict instructions not to invent anything, and their JSON is validated.
  A model can still overstate a pattern or misread a quote. The facts beside each write-up are
  the ground truth.
- **The report agent writes a "future prediction report".** Its prompts frame the simulation as
  a preview of the future and require every claim to come from its graph searches and
  interviews. Treat its confidence as the framing of the prompt, not as evidence of accuracy.
- **Interviews need live agents.** Agents can only be interviewed while their run's environment
  is up (20 minutes after the last round on the public site). After that, the report agent can
  still search everything they did through the graph.
- **The PDF uses a Latin-1 font.** Text in scripts outside Latin-1 (for example Chinese) cannot
  be printed in the briefing PDF.

## Language

- Three groups of prompts inherited from the original code base are still written in Chinese:
  ontology design, persona writing and the simulation config (clock, opening posts, agent
  activity). Each ends with an instruction to answer in the UI language, so their output is in
  English by default. The other prompts, the interview prefix, the graph-memory episodes and
  the backend's messages are in English. Many code comments are still in Chinese.
- The interface is available in English and Chinese. `locales/languages.json` lists more
  languages, but only those with a strings file are offered.

## The public site and the infrastructure

- **Capped by design.** 5 new runs a day in total, 1 per visitor, one simulation at a time, 10
  rounds, 20 chats per visitor and 150 a day. A visitor's allowance is used when the run starts,
  even if a later step fails.
- **Visitors are identified by IP address** (Railway's `X-Real-IP`). People behind one shared
  address share one allowance.
- **Development server, single process.** Flask runs on Werkzeug's development server in one
  process. State such as running simulations and task progress lives in that process, so it
  cannot be scaled to several workers as is, and a restart ends live runs and kept-alive agents.
- **Zep free tier.** Graph ingestion and memory write-back count against the Zep plan, which can
  run out on a busy day.
- **Railway config-as-code.** `railway.json` is deprecated after 2026-12-01; its health check and
  restart policy need to move into the service settings.

## People, privacy and responsibility

- **Real people are simulated.** If the evidence names real people and organisations, the
  simulation puts words in their mouths. Those posts are fiction written by a model. Do not
  quote them as anything a real person said.
- **Runs on the public site are public.** Every run, including its question, its seed text and
  everything the agents wrote, appears in the shared history. Do not paste anything private.
- **The live-data connector is aggregate only.** The optional God's Eye View connector refuses
  tools that identify or follow individual people, aircraft or vessels, and camera or
  licence-plate tools. It is off on the public site.
