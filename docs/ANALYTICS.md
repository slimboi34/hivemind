# Analytics, the briefing and the PDF

This page documents everything Hivemind computes after (and during) a run: the Analytics
page, run dynamics and health, cascade trees, the cast tree, the "What happened" recap, the
briefing, and the briefing PDF. For each number it gives the exact definition used in the
code.

One rule holds for all of it: **measurement never changes the prediction.** These modules
only read files a run already wrote. Nothing here feeds back into the simulation, the
knowledge graph or the report agent.

## Contents

- [Where the data comes from](#where-the-data-comes-from)
- [How actions are classified](#how-actions-are-classified)
- [The Analytics page](#the-analytics-page)
- [Activity analytics (`/analytics`)](#activity-analytics-analytics)
- [Run dynamics (`/dynamics`)](#run-dynamics-dynamics)
  - [Cascade trees](#cascade-trees)
  - [Blind turns and feed concentration](#blind-turns-and-feed-concentration)
  - [Run health checks](#run-health-checks)
  - [Engagement consensus](#engagement-consensus)
- [The cast tree (`/cast`)](#the-cast-tree-cast)
- [What happened (`/recap`)](#what-happened-recap)
- [The briefing (`/briefing`)](#the-briefing-briefing)
- [When the write-ups are generated](#when-the-write-ups-are-generated)
- [The briefing PDF](#the-briefing-pdf)
- [How to read these numbers](#how-to-read-these-numbers)

## Where the data comes from

| Source | Written by | Used for |
| --- | --- | --- |
| `twitter/actions.jsonl`, `reddit/actions.jsonl` | the simulation subprocess, one line per action with enriched context (target post text and author, etc.) | activity analytics, the recap, the briefing |
| `twitter_simulation.db`, `reddit_simulation.db` (OASIS SQLite) | OASIS | cascade trees (`trace`, `post`, `comment`, `user` tables), blind turns, feed concentration |
| `run_state.json` | the Flask monitor thread | planned rounds, status, `ready_for_report` |
| `simulation_config.json` | setup (and joiners mid-run) | roster, entity types, configured stance, origin of each account, minutes per round, the question |
| `reddit_profiles.json`, `twitter_profiles.csv` | setup | the roster for "silent agents"; bios for the cast tree |
| `cast_progress.json`, `cast_growth.json` | setup, the subprocess | the cast tree |
| `simulation.log` | the subprocess | counting `[feed-error]` lines |

Actions are read through `SimulationRunner.get_all_actions`, which turns each JSONL line
into `{round_num, timestamp, platform, agent_id, agent_name, action_type, action_args,
result, success}`. Round events (`round_start`, `round_end`, …) are not actions. Round 0 is
the opening posts.

**Interviews are excluded everywhere** (`EXCLUDED_ACTIONS = {"INTERVIEW"}`), so questioning
agents after a run never changes its numbers.

## How actions are classified

`services/simulation_analytics.py` puts every action type into one of five categories.
Interactions (support, oppose, reply) point from the acting agent to the author of the
content they acted on, found in the action's enriched arguments.

| Category | Action types | Points at (field in `action_args`) |
| --- | --- | --- |
| **post** | `CREATE_POST` | (no target) |
| **support** | `LIKE_POST` | `post_author_name` |
| | `REPOST`, `QUOTE_POST` | `original_author_name` |
| | `LIKE_COMMENT` | `comment_author_name` |
| | `FOLLOW` | `target_user_name` |
| **reply** | `CREATE_COMMENT` | `post_author_name` |
| **oppose** | `DISLIKE_POST` | `post_author_name` |
| | `DISLIKE_COMMENT` | `comment_author_name` |
| | `MUTE` | `target_user_name` |
| **passive** | everything else: `DO_NOTHING`, `SEARCH_POSTS`, `SEARCH_USER`, `TREND`, `REFRESH`, … | (no target) |

"Support" therefore means amplifying or approving someone (a like, a repost, a quote, a
follow), and "oppose" means a dislike or a mute. Neither is a measure of what anyone thinks
about the question. A quote post counts as support for the quoted author even if the quote
argues against them.

An interaction an agent aims at itself (liking its own post) is counted as a
`self_interaction` and left out of the network.

## The Analytics page

`/simulation/<id>/analytics` (`frontend/src/views/AnalyticsView.vue`). It loads
`/analytics`, `/dynamics`, `/recap` and `/briefing` together and, while the run is live,
refreshes every 5 seconds. Top to bottom:

| Section | Component | Data |
| --- | --- | --- |
| Briefing | `Briefing.vue` | `/briefing` |
| What happened | `WhatHappened.vue` | `/recap` |
| Cast tree | `CastTree.vue` | `/cast` |
| Run health badge | `HealthBadge.vue` | `/dynamics` → `health` |
| KPIs | in the view | `/analytics` → `totals`, `rounds`, `run` |
| How posts spread (gauges, orphans, consensus) | `BranchingPanel.vue` | `/dynamics` → `cascades.summary`, `orphans`, `consensus` |
| Biggest conversations | `CascadeForest.vue` | `/dynamics` → `cascades.top` |
| Influence network with replay | `InfluenceNetwork.vue` | `/analytics` → `agents`, `edges`; group colours from `/cast` |
| Agent drill-down | `AgentDetail.vue` | the selected agent |
| Top influencers | `InfluencerBars.vue` | `/analytics` → `agents` |
| Activity per round | `ActivityChart.vue` | `/analytics` → `rounds` |
| Most-engaged posts | `TopPosts.vue` | `/analytics` → `top_posts` |
| Action mix | `ActionMix.vue` | `/analytics` → `action_types` |

`?agent=<name>` in the URL selects an agent, so a view can be shared.

**KPIs:**

| KPI | Definition |
| --- | --- |
| Actions | `totals.actions`: every logged action except interviews. |
| Agents | `totals.agents_active`: agents with at least one action. |
| Posts | `totals.post`: number of `CREATE_POST` actions (opening posts included). |
| Interactions | `totals.interactions`: the sum of all support, oppose and reply edges between different agents. |
| Support share | `support / (support + oppose)` over all actions; "–" when there are neither. |
| Rounds | the last round with any action, out of `run.total_rounds`. |

**Influence network encodings.** One node per agent. Node area grows with engagement
received (square-root scale, radius 4 to 24 px). Node fill is the agent's approval
(support share of what it received) on a scale from orange (0) through grey (0.5) to blue
(1); grey when it received neither. The ring colour is the agent's group from the briefing
(media, investors, government, experts, companies, public, organisations, other). Edges are
coloured by kind (support, oppose, reply) and can be toggled. The replay slider shows the
network as it stood after any round: an edge's weight is the sum of its `by_round` counts up
to that round, and agents that had not yet acted are drawn faded.

## Activity analytics (`/analytics`)

`build_analytics(actions, total_rounds)` in `services/simulation_analytics.py`.

Actions are sorted by `(round_num, timestamp)`.

**`rounds[]`**, one row for every round from 0 to `max(last round with an action,
total_rounds − 1)`, so the axis covers the planned run even before late rounds happen:

| Field | Meaning |
| --- | --- |
| `support`, `oppose`, `reply`, `post`, `passive` | actions of that category in the round |
| `total` | all actions in the round |
| `twitter`, `reddit` | actions per platform |
| `active_agents` | distinct agents who did anything that round |

**`agents[]`**, one record per name seen as an actor or as a target:

| Field | Meaning |
| --- | --- |
| `actions`, `twitter`, `reddit` | actions taken, in total and per platform |
| `first_round` | first round the agent acted |
| `given` | actions taken, by category |
| `received` | support, oppose and reply interactions aimed at the agent by others |
| `reach` | number of **distinct** agents who interacted with it |
| `engagement_received` | `received.support + received.oppose + received.reply` |
| `approval` | `received.support / (received.support + received.oppose)`, 3 decimals; `null` if it received neither |

Sorted by `engagement_received`, then `reach`, then `actions`, all descending. "Top
influencers" shows those with `engagement_received > 0`.

**`edges[]`**, one per `(source, target, kind)`: `weight` (count), `first_round`, and
`by_round` (count per round). Sorted by first round.

**`top_posts[]`**: up to 15 posts with engagement greater than 0. A post is identified by
its OASIS `post_id` when known, otherwise by `(platform, author, text)`. Engagement on a post
is `likes + dislikes + reposts + quotes + comments`, where reposts and quotes are credited to
the original post. Sorted by engagement, then by earlier round.

**`action_types`**: count per raw action type, largest first.

**`totals`**: `actions`, `agents_active`, `agents_total` (including agents that were only
ever targets), `rounds`, `posts` (distinct post records seen, including posts known only
because someone engaged with them), `interactions`, `self_interactions`, `twitter`,
`reddit`, and one total per category.

## Run dynamics (`/dynamics`)

`build_dynamics(simulation_id)` in `services/run_dynamics.py`. It combines the activity
analytics above with a reconstruction of each platform's SQLite database
(`services/trace_reader.py`, opened read-only so a live run is never locked). The response
has `run`, `health`, `cascades` (`summary`, `top`, `platforms`), `orphans`, `consensus` and
`analytics_totals`.

### Cascade trees

A **cascade** is an original post and everything that grew from it.

**Building the trees.** Parent-to-child links come from the `trace` table: each `repost` or
`quote_post` row's `info` gives the new post's id and the id it reposted or quoted. Hivemind
does not use `post.original_post_id`, because OASIS rewrites it to the root of the chain,
which would flatten every chain into a star. Comments are attached to their post as leaves
(OASIS comments are flat). Any post that is not a child is a **root**. Roots are ordered by
time.

**Per-tree metrics:**

| Metric | Definition |
| --- | --- |
| `size` (n) | nodes in the tree: the root, its reposts and quotes at any depth, and comment leaves |
| `depth` | the longest path from the root, in links |
| `breadth` | the most nodes at any single depth |
| `virality` (ν) | structural virality (Goel et al. 2016), the mean distance between all pairs of nodes: `ν = 2W / (n(n−1))`, with `W = Σ over edges of s(n − s)`, where `s` is the size of the subtree below the edge. 0 for a single node. Rounded to 3 decimals. |
| `shape` | `orphan` if n = 1; `broadcast` if ν < 2.2 and depth ≤ 1 (a star around the root); otherwise `chain` |
| `derived_posts` | reposts and quotes in the tree |
| `comment_leaves` | `size − 1 − derived_posts` |

**Per-platform summary:**

| Field | Definition |
| --- | --- |
| `posts` | rows in the `post` table (reposts and quotes are posts in OASIS) |
| `derived_posts` | reposts and quotes that created a new post |
| `branching_factor` | `derived_posts / posts`: follow-on posts per post |
| `roots` | number of cascades |
| `orphan_cascades`, `orphan_share` | cascades of size 1, and their share of all cascades |
| `mean_tree_size`, `max_size`, `max_depth` | over all cascades |
| `mean_virality` | mean ν over cascades with more than one node |
| `cascades` | the 25 largest (by size, then depth, then ν), each with its full tree |

**Cross-platform roll-up** (`cascades.summary`): sums of `roots`, `orphan_cascades`,
`derived_posts`, `posts`; `branching_factor` recomputed from the sums; the larger
`max_depth` and `max_size`; the mean of the two platforms' `mean_virality`. `cascades.top`
is the 20 largest trees across both platforms.

`orphans` repeats the orphan count and share and adds the **silent agents**: names in the
profile files that never acted.

### Blind turns and feed concentration

**Blind activations.** An activation is one agent acting in one round, after the opening
posts. It is blind when the agent was shown no feed that round, because building it failed
or there was nothing to show. OASIS records only successful refreshes, so a missing refresh
is the signal. Rounds are recognised two ways because the platforms stamp time differently:
by a shared step counter, or, with wall-clock times, by treating a refresh that follows an
action as the start of a new round. Interviews and sign-ups are not turns. Known limit: a
round in which every refresh failed cannot be told apart from the one before it and counts as
sighted.

`blind_share = blind_activations / activations`.

Before the quote-post patch (see [PIPELINE.md](./PIPELINE.md#inside-the-subprocess)), 17 to 46
percent of Twitter-side turns in stored runs were blind.

**Feed concentration.** Every successful refresh lists the posts it showed. `top_slot_share`
is the share of all those slots taken by the single most-shown post. A high value means one
post filled most feeds: spread came from the recommender, not from people passing it on.

### Run health checks

`_health_checks` grades six checks green, amber or red. The **overall** level is the worst of
them.

| Check | Value | Green | Amber | Red |
| --- | --- | --- | --- | --- |
| Feed visibility | blind activations / activations, both platforms | below 5% | 5% to 15% | 15% or more |
| Effective participation | agents who acted / agents in the profile files | 50% or more | 30% to 50% | below 30% |
| Action mix | support actions / posts | 0.5 or more | 0.2 to 0.5 | below 0.2 |
| Feed concentration | the larger platform `top_slot_share` | below 35% | 35% to 50% | 50% or more |
| Cascade branching | derived posts / posts, both platforms | 0.4 or more | 0.2 to 0.4 | below 0.2 |
| Horizon coverage | `(current_round + 1) / total_rounds`, capped at 1 | 50% or more | 15% to 50% | below 15% |

A check with no data yet (no posts, no refresh traces) is amber. Horizon coverage only
appears once the planned number of rounds is known.

Each non-green check adds a plain-language **reason** (for example "In 22% of turns the agent
was shown no feed, so it could only post or do nothing. Treat how posts spread as
unreliable."). The **headline** is fixed per level:

- green: "This run looks healthy enough to read as a simulated public."
- amber: "This run has warnings — use the forecast carefully."
- red: "This run has serious validity problems — treat conclusions as provisional."

The feed-visibility detail also reports how many `[feed-error]` lines are in
`simulation.log`.

The branching thresholds are deliberately low. Most real posts draw no follow-on either, so
only near-zero spread is treated as a fault.

### Engagement consensus

`_consensus_from_analytics` reads a "consensus" from reactions alone, without asking a model
about anyone's stance.

- `crowd_support_share = support / (support + oppose)` over all actions.
- `mean_agent_approval`: the mean of `approval` over agents that received any support or
  opposition.
- Verdict: `supportive` if the crowd support share is 0.65 or more, `opposed` if 0.35 or less,
  `split` in between, `no_engagement` if there was no support or opposition at all.
- `amplified_agents`: up to 10 agents that received engagement (with their approval).
  `ignored_posters`: up to 15 agents that acted but received nothing.

This measures how warmly the simulated crowd treated each other's posts. It is not a poll of
opinion on the question.

## The cast tree (`/cast`)

`services/run_cast.py` and `CastTree.vue` (a radial D3 cluster layout). It shows run → group
→ kind of participant → participant → the people around that participant.

- The planned cast comes from `cast_progress.json`, written when setup starts and updated as
  each persona is finished, so during Step 2 agents appear as they are spun up (`ready`).
  Older runs without that file fall back to `simulation_config.json`.
- Groups use the same keyword rules as the briefing (below).
- Accounts added around a key actor (`origin: circle`) or that joined because of one
  (`origin: joined` with an anchor) are nested under that actor. A chain of anchors resolves
  to its first link. Newcomers with no anchor sit in their group.
- Each person carries `kind` (`organisation` when the profile's gender is `other`, otherwise
  `person`), `profession`, a 180-character `bio`, configured `stance` and `activity_level`,
  `origin`, `anchor`, `relation`, `why` and `joined_round`.
- Response: `total`, `ready`, `complete`, `origins` (counts of evidence, circle, joined),
  `groups`, plus `growing` (a platform is still playing rounds, so more accounts can join),
  `growth` (the settings in force) and who joined.

## What happened (`/recap`)

`services/run_recap.py`. A plain-language story of the run in time order, built in two
layers.

### Facts (deterministic)

`build_recap_facts` is a pure function over the actions.

**Chapters.** The rounds with any non-passive action are grouped into stretches a reader can
follow (`plan_chapters`):

- if the run spans 2 to 10 simulated days, one chapter per day;
- otherwise, one chapter per round when there are 6 rounds or fewer;
- otherwise 4 chapters of near-equal length (6 for runs longer than 10 days).

A 10-round run at 60 minutes per round (10 simulated hours) gets 4 chapters. Each chapter has a
label ("Round 3", "Rounds 4–6", "Day 2") and a simulated clock span ("Day 1, 09:00–11:59").

**Per chapter:**

| Field | Definition |
| --- | --- |
| `posts`, `replies`, `approving`, `disapproving` | actions in the chapter by category (post, reply, support, oppose) |
| `activity` | the sum of those four |
| `tone` | `approving / (approving + disapproving)`; `null` if neither |
| `people_active`, `returning` | agents who did anything; how many were also active in the previous chapter |
| `loudest` | the 3 agents with the most moves, with how many of those were writing |
| `new_voices`, `new_voice_count` | agents whose first move falls in this chapter (up to 8 named) |
| `standout_posts` | up to 3 posts that drew the most reactions **in this chapter**; the first is one no earlier chapter led with, so each stretch shows something new. `written_in_this_stretch` says whether the post is new or an older post still drawing reactions. |
| `posts_said` | up to 8 posts written in the chapter, most engaged first |
| `top_replies` | up to 3 comments, ranked by likes minus dislikes, then length |
| `pushback` | the post or comment with the most dislikes in the chapter |
| `quiet` | nothing but passive actions happened |

**Whole run:** `run` (`status`, `finished`, `rounds_done`, `rounds_planned`,
`minutes_per_round`, `duration`, `platforms`), `cast` (`people_active`, `roster`, `silent`),
`totals` (`posts` including opening posts, `replies`, `approving`, `disapproving`, `tone`),
`opening` (up to 8 opening posts, merged across platforms), `highlights` (`busiest_chapter`,
`biggest_post`, `most_engaged_people` (5), `most_disliked`, `tone_first`, `tone_last`,
`largest_thread` from the biggest cascade), `ending` (the engagement consensus verdict and
sentence) and `caveats` (health level, headline, up to 3 reasons).

Quotes are copied verbatim from the logs, trimmed to 280 characters at a word boundary.

A run counts as **finished** when its status is `completed` or `stopped`, or when every
platform has logged its last round (`ready_for_report`), even if the agents are still being
kept alive.

### Story (prose)

**Template story** (`template_story`), no model needed. It writes a headline ("N simulated
voices posted and reacted over 10 simulated hours; X's post drew the biggest response."), a
summary, the opening, one short paragraph per chapter, the ending and takeaways. Tone is put
into words: 75% or more approving is "warm", 60% "mostly approving", 40% "mixed", 25%
"mostly disapproving", below that "hostile". A change of less than 8 points between the first
and last chapter is "about the same as before".

**AI story** (`llm_story`). The model receives the facts (slightly trimmed) and must return
JSON with `headline` (25 words at most), `summary`, `opening`, one `chapters` entry per
chapter (`index`, `title`, `story`), `ending` and `takeaways`. The rules it is given:

- use only names, numbers and events in the facts; never invent anything;
- the run covered only its simulated duration, never the dates named in the question;
- no quotation marks unless copied word for word from a text field;
- each chapter uses only its own posts and replies; a quiet chapter is described as quiet;
- "tone" is how warmly posts were received, not opinion; say "reactions were warmer", never
  "opinion shifted";
- call the platforms "Info Plaza" (the short-post feed) and "Topic Community" (threaded
  discussion), never Twitter or Reddit;
- no jargon ("cascade", "agent", "round", "engagement");
- mention the main caveat once if the run's health is amber or red.

Temperature 0.4, up to 4,096 tokens, 2 attempts. The reply is validated and any missing piece
is taken from the template, so a malformed reply never breaks the page.

**Cache.** `recap.json` stores the story with a fingerprint
`v1|<number of actions>|<last action timestamp>|<finished>`. `GET` returns the cached AI story
when the fingerprint matches, otherwise the template (`story_stale: true` if an older AI story
exists). Interviews are excluded from the fingerprint, so they never make the story stale.

## The briefing (`/briefing`)

`services/run_briefing.py`. The recap tells the story; the briefing answers a
decision-maker's questions: what is the bottom line, where do the simulated voices agree and
split, how did each kind of actor react and what would they do next, how would each company
react, and what should I watch.

### Groups

Each person is placed in a broad group by keyword-matching the entity type the ontology gave
them. The first group with a matching keyword wins, in this order:

| Group | Keywords (substring of the lower-cased type) |
| --- | --- |
| Media | media, news, press, journal, outlet, reporter, broadcast, publication |
| Investors and analysts | invest, analyst, fund, bank, trader, shareholder, broker, venture |
| Government and regulators | government, politic, legislat, committee, regulat, agency, ministry, court, senat, congress, parliament, authority, department, military |
| Experts and institutions | legal, law, universit, professor, expert, research, academ, scien, ngo, nonprofit, thinktank, institut, union, association, advocacy |
| Companies and executives | company, corporat, business, brand, firm, enterprise, startup, executive, ceo, founder, manufactur, vendor, supplier, competitor, retailer, platform |
| Public voices | person, people, citizen, student, consumer, customer, user, public, resident, fan, employee, worker, individual, influencer, creator, parent, voter |
| Organisations | organization, organisation, group, community |
| Other voices | anything else |

Order matters: `InvestmentAnalystFirm` is an investor and `RegulatoryAgency` is government,
before the generic company words are tried. A bare "official" is deliberately not a
government keyword (a `RugbyOfficial` is not the government). The role types used for added
voices are spelled so they land in the right group.

### Facts (deterministic)

`build_briefing_facts` is a pure function over the actions and the roster
(`simulation_config.json` → `agent_configs`).

- A person's **posts** are `CREATE_POST`s plus `QUOTE_POST`s with text; **replies** are
  comments. Each distinct text per author is one record, so an opening post published on both
  platforms counts once.
- Support and opposition given and received are counted per person and per **group pair**
  (who backed whom).

Per group:

| Field | Definition |
| --- | --- |
| `members`, `active` | people in the group; those who posted, replied, supported or opposed |
| `posts`, `replies` | written by the group |
| `approving_received`, `disapproving_received`, `replies_received` | reactions to the group's members |
| `reception` | `approving_received / (approving_received + disapproving_received)`: how warmly their posts were received, not their opinion |
| `approving_given`, `disapproving_given` | reactions the group gave |
| `starting_stances` | how setup cast them (`supportive`, `opposing`, `neutral`, `observer`), as background |
| `voices` | the 5 most-heard members (reactions received, then amount written) |
| `silent` | up to 8 members who did nothing |
| `said` | up to 6 verbatim posts: most-reacted first, at most 2 per author, so a group is not represented only by its loudest voice |

Also: **companies** (up to 12 members of the companies group who wrote something, each with
reception, starting stance and 2 posts), **most_backed_posts** (top 6 by approving reactions),
**most_disputed_posts** (top 3 by disapproving reactions), **who_backed_whom** (group-to-group
approving and disapproving counts, top 8 pairs), **run** (status, finished, duration, people
total and active, posts, replies, approving, disapproving, overall reception), **cast mix**
(evidence, circle and joined counts, the share of all posts and replies written by added
voices, their names, and a one-sentence note for the reader), and **caveats** (the health
level, headline and up to 4 reasons).

### Confidence (deterministic)

`confidence_for` sets how much weight the run can bear:

1. Start from the health level: green → high, amber → medium, red → low.
2. If fewer than 20 posts and replies were written, or fewer than 30% of the cast took part:
   low. Otherwise, if it was high but fewer than 60% took part: medium.
3. If the run has not finished: low.

Labels: high is **Solid**, medium is **Directional**, low is **Thin**. A one-line "why" says
how many took part and repeats the health headline if it is amber or red.

### Reading (prose)

**Template reading** (`template_reading`), no model needed: a bottom line naming the group
that wrote most and the overall approving share; what it means (the warmest-received group,
groups that stayed silent, the most-backed post); consensus points from the top 3 backed posts
(moderate if 3 or more approving reactions, else weak); splits from the top 2 disputed posts;
one reaction paragraph per group; each company's position as its first post. No "likely next"
or "watch" items, because those need inference.

**AI reading** (`llm_reading`). The model gets the facts (silent lists removed, platform names
replaced with Info Plaza and Topic Community) and returns JSON:

```json
{
  "bottom_line": "1-2 sentences answering the question as far as this run can",
  "what_it_means": ["3-4 implications"],
  "consensus": [{"point": "...", "held_by": ["group labels"], "strength": "strong|moderate|weak"}],
  "splits": [{"issue": "...", "side_a": "...", "side_b": "..."}],
  "groups": [{"key": "...", "stance": "supportive|critical|cautious|divided|neutral|quiet", "reaction": "...", "likely_next": "..."}],
  "companies": [{"name": "...", "position": "...", "likely_move": "..."}],
  "watch": ["3-4 signals that would confirm or break this reading"]
}
```

Its rules: use only names, numbers and positions in the facts, with no outside knowledge;
phrase findings as what the simulated actors did; agreement means several groups arguing the
same point or one group's point drawing approval from others, and an empty list is the right
answer when there is none; `likely_next` and `likely_move` are inferences tied to what the
actor said; a group or company that wrote nothing is "quiet"; added voices (listed in
`run.cast.added_names`) are evidence of how affected people react, never the position of a
named actor, and no consensus or company move may rest on them alone; no jargon; no quotation
marks unless copied exactly.

Temperature 0.3, up to 8,192 tokens, 2 attempts. `_merge_reading` then validates it: consensus
`held_by` must name real groups and `strength` must be valid; a group with no writing is forced
to `quiet`; any missing group or company is filled from the template; an empty consensus or
splits list from the model is kept, because "no real agreement" is a finding.

**Cache.** `briefing.json` stores the reading with a fingerprint: the first 16 hex characters
of a SHA-1 of the facts (without the run status). `GET` returns the cached reading when it
matches the current facts, otherwise the template (`reading_stale: true` if an older AI
reading exists). The response also has `confidence`, `reading_source` (`llm` or `template`),
`written_at` and `can_write` (an LLM key is set and the run has some writing).

## When the write-ups are generated

- **While a run is live**, the page shows template versions, which update every 5 seconds.
- **The first time anyone opens Analytics after a run finishes**, the page asks the backend
  (`POST .../recap` and `POST .../briefing`) to write the AI versions. Each is one model call,
  cached, so later visitors see the stored text without a new call.
- **Rewrite** (locally only) forces a new version with `force: true`.
- **On the public site** the write requests are accepted only for finished runs, at most 3
  times per run for each write-up (the fingerprint can move once or twice as a run settles),
  and forced rewrites are refused. The Rewrite buttons are hidden. Earlier runs show their
  stored briefing and story.
- **The PDF** with `?write=1` (what the Download button requests) writes any missing AI
  version first, so the document never ships with a template when the model is available.

## The briefing PDF

`GET /api/simulation/<id>/consensus-report.pdf`, built in memory by
`services/consensus_report.py` with PyMuPDF on A4 pages in the brand colours. Order:

1. **Cover**: the date, whether the run has finished, the simulation id and the question.
2. **The bottom line**, with "How far to trust this" (the confidence label and why), four
   key figures (people who took part, posts and replies, reactions, share approving), the
   note on added voices, then **What it means**.
3. **Consensus**: where the simulated voices agree, with strength and who holds each point.
4. **Disagreement**: where they split, side by side.
5. **Reactions**: each group's stance, a bar for how warmly its posts were received, its
   reaction, its likely next step, and one verbatim post.
6. **Companies**: each company's position and likely move.
7. **What to watch** (AI reading only).
8. **The story**: "What happened" from the recap, chapter by chapter.
9. **Appendix: Run diagnostics**: the health badge, reasons and every check; how posts spread
   (follow-ons per post, conversation starters, posts nobody picked up, longest chain, silent
   participants); the 6 biggest conversations.
10. **Appendix: Prediction report excerpt**: the first 35 lines of the report agent's
    `full_report.md`, if a report exists for the run.

Every page's footer reads "Hivemind briefing · a simulation of how people might react, not a
record of real events". The PDF uses the base-14 Helvetica font, which only covers Latin-1:
typographic punctuation is converted, and characters outside Latin-1 (for example Chinese)
cannot be printed.

## How to read these numbers

- **These are reactions inside a simulation**, chosen by a language model playing each
  persona. "Support share", "reception" and "consensus" measure how the simulated accounts
  treated each other's posts. They are not polls and not forecasts of real behaviour.
- **Small runs are noisy.** A 10-round run with a few dozen agents produces a few hundred
  actions. One extra like can swing a percentage. Read the health badge and the confidence
  label before the bottom line.
- **Runs are not repeatable.** Agent selection and feeds are random and unseeded, so two runs
  of the same setup differ. A difference between two runs is not evidence of anything unless
  it is larger than the run-to-run spread.
- **Spread is shaped by the recommender.** High feed concentration or low branching mean the
  platform decided what people saw more than the people did.

See [LIMITATIONS.md](./LIMITATIONS.md) for the full list, and
[research/INFORMATION_DYNAMICS.md](./research/INFORMATION_DYNAMICS.md) for the analysis that
motivated these checks.
