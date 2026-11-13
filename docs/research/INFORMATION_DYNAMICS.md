# Information dynamics in Hivemind: how the effect happens, and how to make it accurate

Status: research and design note, November 2026. Nothing in here is implemented yet.

Scope: how information spreads and opinions move inside a Hivemind simulation, what limits the
accuracy of its forecasts, and a ranked plan to (A) measure and explain the dynamics and
(B) improve the model. Every statement about the engine is tied to a file and line. Every
statement about the example run comes from its sqlite trace databases.

Code base examined:
- Hivemind `dev` at `959a70f`.
- `camel-oasis` 0.2.5 and `camel-ai` 0.2.78 in `backend/.venv`.

Paths in the form `oasis/...` are relative to `backend/.venv/lib/python3.12/site-packages/`.

Example run: `backend/uploads/simulations/sim_168d7ecb477b/`.
- Scenario: Jensen Huang resigns as Nvidia CEO.
- Size: 74 agents, 10 rounds, 246 logged actions.
- Report: `report_a2ab76152b1f`.

---

## 0. Summary

**What the engine is today.** On Twitter, a Hivemind run is not a network diffusion process. Every agent starts with
zero follows, and none were formed in the example run. Nearly all exposure comes from a semantic-similarity recommender
that hands each active agent 2 posts. On Reddit, every agent gets 5 posts drawn uniformly at random. An LLM then picks
an action. Information therefore travels as one-hop broadcasts chosen by the recommender. It does not move through
chains of resharing.

What agents "believe" is never represented. It exists only as persona text plus a growing chat transcript. Over a
short run, what agents say is mostly a function of how the LLM wrote their persona.

**What the example run shows.**

- **No branching:** All 18 repost/quote cascades are one level deep. The largest is a star of 6 nodes. The empirical
  branching factor is 0.26.
- **Blind agents:** 46% of Twitter LLM activations saw an empty feed. By the final step it was 80%. The cause is an
  OASIS bug: a quote post at the head of a feed crashes the refresh.
- **Concentration comes from the recommender:** 57% of the final Twitter recommendation slots point at one original
  post. This comes from embedding geometry and quote duplication, not from popularity.
- **Reddit's ranking is inert:** "hot" ranking never takes effect, because there were 32 posts and the pool holds 100.
- **Dead config fields:** Many configured parameters are never read. These include the recommender weights, stance,
  sentiment bias, influence weight and posts per hour.
- **No forecast or uncertainty:** The report is written from one stochastic run. It has no probabilities and no
  uncertainty, and the run covered 10 simulated hours of a two-week question.

**Top five proposals** (detail in Section 4):

| # | Proposal | Group | Why | Effort |
|---|---|---|---|---|
| 1 | B1. Correctness fixes: quote-crash, frozen recency, Reddit feed, clocks, activation, prompt bias | B | Everything else measures or ensembles a process that is partly broken | S-M, 2-3 days |
| 2 | A1-A3. Trace event store, run health card, cascade metrics (depth, structural virality, branching) | A | Reads data that already exists; makes "how it spread" visible; zero LLM cost | M, 3-4 days |
| 3 | B2. Seeded ensembles with prediction intervals (plus forecast extraction, B8) | B | A single run is one draw from a high-variance process; intervals make forecasts scoreable | M, 4-6 days, K x run cost |
| 4 | A5. Stance trajectories, polarization indices, "interaction value-added" | A | Turns implicit opinions into numbers and tests whether interaction matters at all | M, 3-5 days, ~5% of run cost |
| 5 | B3. Follow graph from the knowledge graph plus a real ranker, with algorithm variants | B | Without a network, multi-step cascades are structurally impossible | M-L, 1-2 weeks, ~0 LLM cost |

**Gate.** The backtesting harness in Section 5 is what decides whether any B change ships.

---

## 1. How the engine works today, stated mathematically

### 1.1 The pipeline as a stochastic process

```
seed docs ─▶ Zep graph ─▶ entities ─▶ personas (LLM) ─▶ config (LLM) ─▶ OASIS run (Twitter ∥ Reddit) ─▶ actions ─▶ Zep ─▶ ReportAgent
                                                                        │
                    per round r:  activation S_r ─▶ rec-table update ─▶ per agent: refresh feed ─▶ LLM picks tool call(s) ─▶ DB write
```

Write the platform state after round $r$ as $X_r$. It holds:
- users and posts;
- likes, follows and comments;
- the recommendation table;
- each agent's memory.

One round is

$$X_{r+1} = \Phi\big(X_r,\ S_r,\ \{a_{i,r}\}_{i\in S_r}\big),\qquad a_{i,r}\sim \pi_{\text{LLM}}\big(\cdot \mid \text{persona}_i,\ M_{i,r},\ o_{i,r}(X_r)\big)$$

Here $S_r$ is the active set, $o_{i,r}$ is the observation (the feed), and $M_{i,r}$ is agent memory. Today the report
is generated from **one** realisation of $(X_0,\dots,X_R)$. Sections 1.2–1.9 specify each piece.

### 1.2 Activation (who acts in a round)

The code is `backend/scripts/run_parallel_simulation.py:1040-1092`. It is called once per platform per round, at lines
1239 and 1438, with independent draws. The `random` module is never seeded anywhere in Hivemind or OASIS.

Notation:
- round index $r=0,\dots,R-1$;
- $\Delta$ = `minutes_per_round`;
- hour $h_r=\lfloor r\Delta/60\rfloor \bmod 24$ (computed at lines 1236 and 1435).

For each agent with `active_hours` $H_i$ and `activity_level` $a_i$:

$$C_r=\{\,i:\ h_r\in H_i,\ U_{ir}<a_i\,\},\quad U_{ir}\sim\mathcal U(0,1)\qquad\text{(lines 1066-1075)}$$

$$T_r=\big\lfloor V_r\,\mu(h_r)\big\rfloor,\quad V_r\sim\mathcal U(m_{\min},m_{\max})\qquad\text{(line 1063)}$$

$$S_r=\text{uniform sample without replacement of }\min(T_r,|C_r|)\text{ agents from }C_r\qquad\text{(line 1077)}$$

The multiplier is $\mu(h)=1.5$ for peak hours, $0.05$ for off-peak hours and $1.0$ otherwise (lines 1055-1061). The
config also defines `morning_activity_multiplier` (0.4) and `work_activity_multiplier` (0.7), but nothing reads them
(`simulation_config_generator.py:640-645`).

The marginal probability of acting is

$$P(i\in S_r)=\mathbb 1[h_r\in H_i]\;a_i\;\mathbb E\!\left[\min\!\big(1,\,T_r/|C_r|\big)\,\middle|\,i\in C_r\right].$$

In the example run, $\mathbb E|C_r|=\sum_{i:h_r\in H_i}a_i\approx 11$ at the peak hours 0–1, while $T_r\sim\mathcal
U(12,82)$. The candidate pool therefore binds, and `agents_per_hour_min/max` and the peak multiplier do nothing. At
off-peak hours (2–5 here) the target is 0–2 and binds the other way. Activation is memoryless: being replied to, quoted
or mentioned does not make an agent more likely to come back.

**Configured but never read.**
- In `AgentActivityConfig` (`simulation_config_generator.py:52-81`):
  - `posts_per_hour`, `comments_per_hour`;
  - `response_delay_min/max`;
  - `sentiment_bias`, `stance`;
  - `influence_weight`. Its only use is the fallback when no seed poster matches (line 799).
- In `PlatformConfig` (`:131-144`, set at `:341-359`):
  - `recency_weight`, `popularity_weight`, `relevance_weight`;
  - `viral_threshold`, `echo_chamber_strength`.

A repository-wide grep finds no consumer for any of these. The `stance` and `sentiment_bias` the config LLM writes for
each agent never reach the agent's prompt.

### 1.3 Clocks

| Platform | Time used for `created_at`, recency and hot score | Code |
|---|---|---|
| Twitter | integer `time_step`, advanced once per executed `env.step` (rounds with no active agent are skipped and do not advance it) | `oasis/environment/env.py:198`, `run_parallel_simulation.py:1247-1251` |
| Reddit | $t = t_0 + 60\times(\text{wall-clock elapsed})$ | `oasis/clock/clock.py:28`, `oasis/social_platform/platform.py:77` |

Neither clock equals the simulated hour. In the example run the Reddit clock spans 14:52 → 17:37 (2 h 45 min) for 10
configured hours, because the run took about 3 minutes of wall-clock time. LLM latency therefore changes the Reddit
time axis.

### 1.4 Feed construction on Twitter (TwHIN-BERT recsys)

`oasis.make` builds the Twitter platform with `recsys_type="twhin-bert"`, `refresh_rec_post_count=2`,
`max_rec_post_len=2` and `following_post_count=3` (`oasis/environment/env.py:78-85`). Before each step, the
recommendation table is rebuilt (`env.py:152` → `platform.py:328-398` → `recsys.py:419-606`):

$$u_i=\mathrm{TwHIN}\big(\text{bio}_i\ \Vert\ \text{" \# Recent post: "}\ \Vert\ \text{last own post}_i\big)\quad(\texttt{recsys.py:509}),\qquad v_j=\mathrm{TwHIN}(\text{content}_j)$$

$$R_j=\ln\frac{271.8-(\tau_j-t_j)}{100},\qquad \text{score}_{ij}=\cos(u_i,v_j)\cdot R_j\quad(\texttt{recsys.py:470-472, 583})$$

$$\text{Rec}_i=\operatorname{top}_2\,\text{score}_{i\cdot}\quad(\texttt{recsys.py:585})$$

When there are 2 or fewer posts, every user gets all of them.

Four implementation facts change the dynamics:

1. **Recency is frozen.**
   - $R_j$ is appended to a global list once, when post $j$ is first indexed, and never recomputed.
   - $\tau_j$ is the indexing step, so $\tau_j-t_j\in\{1,2\}$ and $R_j\in[0.992,0.996]$ for every post.
   - The ranking is therefore pure cosine similarity between a profile and a post.
   - The list can also become misaligned with `t_items` when a step's posts are re-indexed. That is harmless only
     because all values are about 1.
2. **No popularity or follower term.**
   - `u_items` (follower counts) is computed at line 441 and never used.
   - `enable_like_score` defaults to `False` (line 429).
   - The OASIS paper describes a score that also includes a follower factor. This installed version does not have one.
3. **Quotes are embedded as their original.**
   - `quote_post` stores the *original* post's text in `content` and the quoter's words in `quote_content`
     (`platform.py:504-561`). In the run, 16 of 16 quote rows have `content` equal to the original.
   - The recommender therefore cannot see the quoter's stance.
   - Every quote is a near-duplicate of its source and competes for the same slots.
4. **In-network posts.**
   - The refresh adds the top 3 posts by all-time `num_likes` from followed accounts, with no recency term
     (`platform.py:285-299`).
   - Agents start with no follows (`agents_generator.py:614-649` builds no edges) and formed none, so this term was
     empty for the whole run.

Refresh (`platform.py:258-326`): if the rec list has at least `refresh_rec_post_count` entries, the refresh takes a
uniform sample of that many (`:276-278`). With both values equal to 2, a Twitter agent sees at most 2 recommended
posts plus up to 3 followed posts.

### 1.5 Feed construction on Reddit (hot score)

Reddit is configured with `recsys_type="reddit"`, `max_rec_post_len=100`, `refresh_rec_post_count=5` and
`show_score=True` (`env.py:89-97`).

$$\text{hot}_j=\operatorname{sign}(s_j)\log_{10}\max(|s_j|,1)+\frac{t_j-1134028003}{45000},\qquad s_j=\text{likes}_j-\text{dislikes}_j\quad(\texttt{recsys.py:168-195})$$

This is the formula from Reddit's archived open-source `_sorts.pyx`.

$$\text{Pool}=\operatorname{top}_{100}\text{hot}\ \text{(identical for all users)},\qquad F_i=\text{uniform sample of 5 from Pool}\quad(\texttt{recsys.py:213-259},\ \texttt{platform.py:276-278})$$

When there are 100 or fewer posts, the pool is every post, so $P(j\in F_i)=5/|\text{posts}|$ for all $j$. Votes and
recency have no effect. Even above 100 posts, the hot score only decides membership of a 100-post pool; it does not
order the feed. The example run never exceeded 32 posts.

### 1.6 What an agent sees

The observation is built in `oasis/social_agent/agent_environment.py:118-135`. The template (`:49-53`) uses only the
groups block and the posts block. Follower and following counts are computed and then discarded, because the template
has no slot for them.

The posts are a JSON list from `platform_utils.py:75-186`. Each post has:
- `post_id`;
- `user_id` (a number, not a name);
- `content`, with wrappers such as "User 12 quoted a post from User 3...";
- `created_at`;
- likes and dislikes, or `score` on Reddit;
- `num_shares`, `num_reports`;
- `comments`.

**Agents never see who wrote a post.** "Donald Trump" and "Yahoo Finance" both appear as `User N`. Source credibility
and identity cues reach an agent only if the text names its author.

### 1.7 How an agent decides

The system prompt is `oasis/social_platform/config/user.py:50-77` for Twitter and `:79-111` for Reddit. It contains:
- the objective ("You're a Twitter user ... choose some actions");
- the persona text, with a median of 4,734 characters in the run;
- on Reddit, also gender, age, MBTI and country.

The user turn (`oasis/social_agent/agent.py:130-134`) reads: *"Please perform social media actions after observing the
platform environments. Notice that don't limit your actions for example to just like the posts."* The observation
template adds: *"pick one you want to perform action that best reflects your current inclination ... Do not limit your
action in just `like` to like posts."* Both sentences push the model away from liking.

**Available actions** (`run_parallel_simulation.py:177-202`):

| Platform | Actions |
|---|---|
| Twitter | `create_post`, `like_post`, `repost`, `follow`, `do_nothing`, `quote_post` |
| Reddit | the above plus `dislike_post`, `create_comment`, `like/dislike_comment`, `search_posts`, `search_user`, `trend`, `refresh`, `mute` (no repost or quote) |

The policy is

$$a_{i,r}\sim\pi_{\theta}\big(\cdot\mid \text{sys}_i,\ M_{i,r},\ o_{i,r},\ \mathcal A_p\big).$$

It is one model call (`max_iteration=1`, `agent.py:112`) that may emit several parallel tool calls. In the example run
it emitted 1 almost every time.

- **Model:** `claude-haiku-5-5` through Anthropic's OpenAI-compatible endpoint (`.env`).
- **Sampling:** `create_model` passes no config (`run_parallel_simulation.py:1034-1037`), and camel's default
  temperature is `None`, so sampling is whatever the provider defaults to. Claude 5 rejects `temperature` anyway (commit
  `041827d`). Sampling diversity cannot be tuned and the LLM draw cannot be seeded.

### 1.8 Memory

`SocialAgent` subclasses camel's `ChatAgent` and passes no memory settings (`agent.py:106-111`). camel builds a
`ChatHistoryMemory` with `window_size=None` (`camel/agents/chat_agent.py:477-487`). For a model name camel does not
know, the token limit defaults to 999,999,999 (`camel/types/unified_model_type.py:64-71`). Memory is therefore

$$M_{i,r+1}=M_{i,r}\ \Vert\ \big(o_{i,r},\ \text{tool calls},\ \text{tool results}\big)$$

It has no forgetting, no summarisation and no retrieval scoring. Generative Agents (Park et al. 2023), by contrast,
scores memories by recency, importance and relevance.

Consequences:
- The prompt grows linearly with each activation, so token cost per agent grows roughly quadratically over a long run.
  For the configured 168-hour run (168 rounds, not the 10 actually run), an agent with activity 0.5 could be activated
  about 50 times.
- Long contexts are used unevenly (Liu et al. 2024, "lost in the middle").
- Twitter and Reddit instances of the same persona share nothing.
- OASIS agents never read Zep. `run_parallel_simulation.py` contains no Zep calls. The "memory" written to Zep is for
  the report only.

### 1.9 How information moves, and why chains cannot form

A post $j$ creates a derived post (repost or quote) in round $r$ through four steps:

$$\mathbb E[\text{offspring}_j(r)]=\sum_i \underbrace{P(i\in S_r)}_{\text{activation}}\cdot\underbrace{P(j\in F_{i,r})}_{\text{exposure}}\cdot\underbrace{P(\text{share}\mid j\text{ seen})}_{\text{LLM decision}}.$$

For a second generation, the derived post must itself be exposed to other agents. On real Twitter that happens through
the resharer's followers. Here it can happen only if the recommender picks the new row, and four things work against
that:
- there is no follow graph;
- repost rows have empty `content`;
- quote rows embed as the original text;
- a quote at the head of a feed crashes the refresh (Section 3.1).

OASIS also rewrites `original_post_id` to the **root** for reposts of reposts and quotes of quotes
(`platform.py:430-561`). The true parent survives only in the `trace` table (`reposted_id`, `quoted_id`).

Plugging in the example run's Twitter numbers:
- 7.6 activations per round;
- 54% of them with a non-empty feed;
- 2 posts per feed;
- 22% of impressions ending in a share.

That gives about 1.8 derived posts per round spread across about 50 posts. Over 10 rounds that is about 0.35 offspring
per root, against the observed 18/51 = 0.35. The bottlenecks are exposure slots and blind feeds, not how appealing the
content is.

### 1.10 Where opinions live

There is no opinion variable. An agent's position on, say, "Huang's exit hurts Nvidia" is implicit in three things:
- the persona text, written by the LLM from the knowledge-graph entity (`oasis_profile_generator.py:721-813`);
- the transcript of posts it has seen;
- the base model's priors.

Opinion change is in-context persuasion with an unknown update rule. The literature reports systematic tendencies in
LLM agents:
- herding (OASIS paper; Weng et al. 2025);
- sycophancy (Sharma et al. 2024);
- drift toward the scientific or official consensus (Chuang et al. 2024);
- reduced variance and flattened groups (Bisbee et al. 2024; Wang et al. 2025; Park et al. 2024; Boelaert et al. 2025).

In a 10-round run, the median agent acts about once per platform and sees 2–5 posts. Final positions are therefore
mostly the initial conditions, meaning the LLM's view of each entity. Proposal A5 shows how to measure how much
interaction actually adds.

### 1.11 What is logged, and what the analytics see

- **Runner log.** `run_parallel_simulation.py:657-746` copies new `trace` rows into `{platform}/actions.jsonl`. It
  drops `refresh` (line 611), so exposures are not in the JSONL. It keeps only the whitelisted arguments at lines
  709-727. `reposted_id` is not on that list, so a repost's parent is lost.
- **Context enrichment.** `_enrich_action_context` (`:749` ff.) adds author names. For `CREATE_COMMENT` it needs
  `post_id`, but OASIS's comment trace stores only `content` and `comment_id`. All 44 comments in the run therefore
  have no target author.
- **Double logging.** Round 1 reads the trace from rowid 0 (`:1169`, `:1257`). The 22 seed posts are therefore logged
  twice, in round 0 by `action_logger` and again in round 1. `action_logger.py:98,271` also hard-codes 2 rounds per
  hour for `total_rounds`, which is why the log shows 336.
- **Analytics.** `simulation_analytics.py` classifies `QUOTE_POST` as support (line 30), although quotes are often
  critical. Its reply edges depend on `post_author_name` for comments (line 46), so the influence network contains no
  Reddit reply edges.
- **The sqlite `trace` table is the ground truth.** It records every refresh, including the exact posts shown, and
  every action with its arguments, including parent ids.

### 1.12 How the report is produced

- **Zep ingestion.** Actions are turned into sentences and sent to Zep in batches of 5. `DO_NOTHING` is dropped
  (`zep_graph_memory_updater.py:228, 371-373`). Zep's LLM extracts facts into the **same graph as the seed documents**.
- **Tools.** The ReportAgent (`report_agent.py:871` ff.) plans 2–5 sections at temperature 0.3 (`:1221`). It writes
  each section with up to 5 tool calls at temperature 0.5 (`:882`, `:1346`). The tools (`:925-960`) are:
  - `insight_forge`: LLM sub-queries plus Zep semantic search (`zep_tools.py:943`);
  - `panorama_search` (`:1143`);
  - `quick_search`;
  - `interview_agents`: an LLM picks agents (`zep_tools.py:1549`) and they answer with their full memory.
- **Prompt framing.** The prompt (`report_agent.py:552-700`) frames the run as "the future preview". It forbids the
  model's own knowledge, and so its base rates, and it asks for no probabilities or uncertainty.
- **What the tools can and cannot count.** No tool reads `actions.jsonl` or the trace databases, so counts, timing,
  cascades and silence cannot be measured. The example report says so itself: its national-security share "reflects the
  sampled retrieval rather than a verified volume count".

---

## 2. What the example run actually did

The figures below come from queries on `twitter_simulation.db`, `reddit_simulation.db` and the JSONL logs. Appendix B
has the queries to reproduce them.

| Quantity | Twitter | Reddit |
|---|---|---|
| Configured vs simulated horizon | 168 h configured, 10 rounds run (hours 0–9) | same; platform clock spans 2 h 45 min |
| Wall-clock duration | about 3 min 20 s | about 2 min 50 s |
| Logged actions (JSONL) | 121 | 125 |
| LLM-driven actions (trace, excluding seed posts) | 77 | 81 |
| Seed posts logged twice | 22 | 22 |
| Action mix (LLM-driven) | 29 posts, 16 quotes, 2 reposts, **0 likes, 0 follows**, 30 `do_nothing` (39%) | 10 posts, 44 comments, 16 likes, 2 dislikes, 4 comment votes, 5 `do_nothing` |
| Activations with a feed / blind | 41 / **35 (46%)**; final step 16 of 20 blind | 59 refreshes for 81 actions; D1 cannot occur (no quotes on Reddit) |
| What blind agents did | 22 `create_post`, 13 `do_nothing` (nothing else possible) | n/a |
| Posts per feed | 2 (no follows, so recommender only) | 5 (uniform from all posts) |
| Distinct posts ever shown | 21 of 69 | 30 of 32 |
| Gini of impressions over posts | **0.86** (top 5 posts = 66% of impressions) | 0.27 (close to uniform, as the code implies) |
| Final rec table | 88 of 148 slots are quotes; **85 (57%) point at one original** (post 35, directly or through its quotes); 48 of 74 users' next refresh would crash | identical 100-post pool for every user |
| Share or engage per impression | 18/82 = 0.22 | 62/295 = 0.21 |
| Engaged post was in the current feed | 18/18 | 62/62; position 0–4 counts 16/11/11/10/14 (no clear order effect) |
| Cascade trees | 51 roots: 42 singletons, sizes 2 (×5), 3, 4 (×2), 6 | comment trees are flat by design (comments attach to posts only) |
| Depth / structural virality | max depth **1**; max ν = 1.67 (a pure 6-node star) | n/a |
| Branching factor $\hat m$ | 18/69 = 0.26 | 44 comments / 32 posts = 1.4, all depth 1 |
| Seed posts engaged | 4 of 22 | 24 of 32 posts have at least one comment |
| Agents with any logged action (seed posts and `do_nothing` included) | 52 of 74 | 47 of 74; 23 agents never posted, commented, voted or shared on either platform |

The population consists only of named knowledge-graph entities:

| Entity type | Count |
|---|---|
| PublicCompany | 14 |
| GovernmentOfficial | 10 |
| RegulatoryAgency | 9 |
| Person | 8 |
| MediaOutlet | 7 |
| Organization | 7 |
| InvestmentAnalystFirm | 7 |
| ExecutiveFigure | 5 |
| LegislativeCommittee | 4 |
| LegalFirm | 3 |

There are no retail investors, employees or members of the general public, although the question asks about "public,
investor and political reaction". Persona generation is homogeneous: 50 of 74 personas are ISTJ.

`EventConfig.scheduled_events` is always empty (`simulation_config_generator.py:725`) and is never read. The earnings
call, the APEC visit and the IPO named in the requirement were therefore never injected into the simulation. The
report still discusses "sentiment stabilizing around earnings".

---

## 3. Weaknesses and biases

### 3.1 Implementation defects that change the dynamics

| # | Defect | Effect on forecasts | Where |
|---|---|---|---|
| D1 | The `quote` branch never sets `num_reports`, so a feed whose first row is a quote raises `UnboundLocalError`. The refresh then fails silently and the agent is told "there are no existing posts" | 46% of Twitter activations were blind. Blind agents can only post or do nothing, so later rounds turn into independent broadcasting. Because quotes rank highly (D3), this gets worse as the run goes on | `oasis/social_platform/platform_utils.py:103-110, 157`; reproduced on a copy of the run DB |
| D2 | Recency is frozen at about 1 | Old posts never fade; the recommender has no notion of news | `recsys.py:470-472` |
| D3 | Quotes embed as their original | Duplicates crowd feeds (57% of slots for one original), and the quoter's stance is invisible to ranking | `platform.py:504-561`, `recsys.py:463` |
| D4 | Reddit feed is uniform over a non-personalised top-100 pool | Votes and recency have no effect; "Reddit dynamics" are random sampling | `recsys.py:213-259`, `platform.py:276-278` |
| D5 | Clocks do not equal simulated time (Twitter skips empty rounds; Reddit runs on 60 × wall-clock) | Recency and hot scores depend on LLM latency; time-based metrics are meaningless | `env.py:198`, `clock.py:28` |
| D6 | Activation multipliers bind the wrong way, two configured multipliers are unused, and there is no seeding | Configured activity does not control activity; runs cannot be reproduced | `run_parallel_simulation.py:1040-1092` |
| D7 | Twitter seed posts are stored in a dict keyed by agent, so a second seed post for the same agent overwrites the first while both are logged | Seed posts can silently disappear (not triggered here: 22 distinct posters) | `run_parallel_simulation.py:1173-1210`; Reddit handles lists at `:1364-1409` |
| D8 | Twelve config parameters are never read (Section 1.2) | The UI and config imply control that does not exist | `simulation_config_generator.py` |
| D9 | Logging gaps: seed posts double-logged, no comment parents, no repost parent, exposures dropped | Analytics undercount replies, overcount round-1 activity, and cannot draw cascades | Section 1.11 |
| D10 | The prompt tells agents twice not to "just like" | 0 likes on Twitter. That kills the popularity signal and inflates content creation, the opposite of real platforms, where most activity is low-cost and most users rarely post (Pew 2019: the top 10% of US adult tweeters produce 80% of tweets; the median user tweets twice a month) | `agent.py:130-134`, `agent_environment.py:49-53` |

### 3.2 Modelling assumptions that limit realism

1. **No social graph.** Diffusion research is about how networks shape spread:
   - IC and LT models (Kempe et al. 2003);
   - complex contagion that needs several exposures (Centola & Macy 2007; Centola 2010; Romero et al. 2011);
   - broadcast versus viral structure (Goel et al. 2016).

   With no follows, none of these mechanisms can occur. The OASIS authors themselves report that their simulated
   cascades are consistently too shallow.
2. **Memoryless, exogenous activation.** Human activity is bursty and self-exciting. Hawkes processes (Hawkes 1971)
   model that self-excitation, and burstiness is documented in Barabási 2005, whose power-law interpretation is
   disputed. Being quoted brings people back. Here it does not.
3. **Tiny, anonymous feeds.** Two posts per Twitter session, with no author names. Real ranking also mixes popularity,
   network and recency (Huszár et al. 2022 show the ranking choice measurably changes what gets amplified).
4. **Unrepresentative population.** Only named entities from the seed documents take part, so the simulated "public" is
   institutions talking to institutions. Population-level questions ("will investors panic?") are answered by a sample
   that contains no ordinary investors.
5. **No explicit beliefs, unbounded transcript memory.** Opinions cannot be read, compared or calibrated. Costs grow
   quadratically on long runs.
6. **Horizon mismatch.** Ten simulated hours are used to answer a two-week question. Scheduled events are never
   injected.
7. **Recommender geometry.** Ranking by cosine similarity on TwHIN `pooler_output` embeddings produces hubs, posts that
   are nearest neighbours of almost everyone (Radovanović et al. 2010). This is the most likely reason a few posts take
   most of the slots. It is a property of the embedding, not of social behaviour.

### 3.3 LLM-agent biases documented in the literature

- **Herding and conformity.**
  - OASIS's Reddit replication of Muchnik et al. 2013 found agents more susceptible to herding than humans in the
    down-vote condition.
  - Weng et al. (ICLR 2025) find all evaluated LLMs conform, more so with larger majorities and more rounds.
  - Cho et al. 2025 show herding depends on how peer information is presented.
  - Humans also herd. Muchnik et al. 2013 found a single initial up-vote raised the chance of a positive rating by 32%,
    but humans corrected negative manipulation.
- **Sycophancy.** Models side with the user or the prevailing view (Sharma et al. 2024).
- **Consensus or "truth" drift.** LLM agents converge on scientific consensus even from wrong starting views unless
  confirmation bias is induced (Chuang et al. 2024). In HiSim, LLM agents struggled to voice opposition, with F1 of
  about 0.34–0.37 on non-supportive stances (Mou et al. 2024).
- **Low variance and flattening.**
  - Persona-prompted LLMs give realistic means but too little variance (Bisbee et al. 2024).
  - They flatten and misportray identity groups (Wang et al. 2025).
  - They collapse to "correct answers" (Park, Schoenegger & Zhu 2024).
  - They show strong, low-variance topic-specific bias (Boelaert et al. 2025).
  - The 50 of 74 ISTJ personas are a local instance of this.
- **Misalignment with demographic opinion.** The gaps are comparable to the Democrat–Republican gap on climate change
  and survive steering (Santurkar et al. 2023).
- **Homogenised writing.** Feedback-tuned models reduce content diversity (Padmakumar & He 2024).
- **Position effects.** Information in the middle of long contexts is used less (Liu et al. 2024). This matters as
  memory grows.
- **Validity bar.** The best-validated LLM social simulators match stylised facts but not distributions:
  - OASIS: normalized RMSE of about 30% on scale, depth and breadth for Twitter15/16 cascades, with depth too low;
  - Larooij & Törnberg 2025: stylised facts only;
  - S³: classical LT/IC baselines matched or beat it on one topic.

  Anthis et al. (2025) argue these tools are ready for exploration but name diversity, bias, sycophancy, alienness and
  generalisation as open problems.

### 3.4 Inference and reporting weaknesses

1. **One draw from a high-variance process.**
   - Social influence makes outcomes unequal and inherently unpredictable (Salganik, Dodds & Watts 2006).
   - Even with rich features, cascade size is only partly predictable (Martin et al. 2016, R² < 0.5).
   - A single unseeded run therefore has no error bar, and two runs of the same config can tell different stories.
2. **No forecast object.** The report states no probabilities, intervals or resolution criteria, so its accuracy cannot
   be scored (Hofman, Sharma & Watts 2017 call for standardised evaluation).
3. **No outside view.** The report prompt forbids the model's own knowledge, which removes base rates. Good forecasting
   practice combines the inside and outside views (Tetlock & Gardner 2015).
4. **Provenance mixing and retrieval bias.** Seed facts and simulated facts share one Zep graph. Semantic retrieval
   returns salient facts, not frequent ones. Silence (`DO_NOTHING`) is dropped.
5. **Interview selection bias.** An LLM picks "the most suitable" agents, and they answer with hindsight from their
   memory.
6. **No validation loop.** Upstream publishes no backtests, and nothing in the repository compares a forecast with an
   outcome.

---

## 4. Proposals

Notation follows Section 1. Effort: S ≤ 1 day, M = 2–5 days, L = 1–3 weeks, for one engineer familiar with the code.

**LLM cost baseline.** The 10-round example made about 160 agent LLM calls. Each prompt holds:
- the persona (about 1.2k tokens);
- tool schemas (about 1k);
- the feed (0.3–3k);
- memory.

That puts a run at roughly **0.5–1M input tokens**. This is estimated from prompt structure, not measured, because the
runner does not log tokens. Proposal A2 adds measurement.

**Not changing site-packages.** `OasisEnv` accepts a `Platform` instance (`oasis/environment/env.py:103`). Every
platform-side change below can therefore live in a Hivemind subclass, for example
`backend/app/simulation/hivemind_platform.py`, passed to `oasis.make(platform=...)` at
`run_parallel_simulation.py:1155` and `:1346`. The venv stays untouched.

### Group A: measurement and insight layers (predictions unchanged)

These read the sqlite traces, JSONL and config that every run already writes. They respect the HIVEMIND.md rule that
new features never change the prediction pipeline. Ranked by value.

#### A1. Trace event store and cascade reconstruction (foundation)

*What.* A read-only module, for example `backend/app/services/trace_reader.py`, that opens
`{platform}_simulation.db` with `mode=ro`. It builds three tables per run.

- **Exposures** $\mathcal E=\{(i,j,t,\text{pos})\}$: one row per post in each `refresh` trace (`info.posts`). Real
  platforms rarely publish this data; Hivemind has it for free.
- **Actions** $\mathcal A=\{(i,\text{type},j,t)\}$: parents come from the trace's `reposted_id` and `quoted_id`, not
  from `post.original_post_id`, which OASIS rewrites to the root. Comment targets come from `comment.post_id`.
- **Activations:** $(i,t)$ pairs with or without a refresh row, which flags blind activations (D1).

*Algorithm.*
1. Map parents: $\pi(\text{new\_post\_id})=\text{reposted\_id}\ \text{or}\ \text{quoted\_id}$.
2. Roots are posts with no parent; build children lists and the tree for each root.
3. For Reddit, comments and likes are leaves under their post.
4. Map Twitter steps to rounds through `actions.jsonl` round markers.
5. Remove the round-1 duplicates of seed posts (D9).

*Plugs into.* A new `GET /api/simulation/<id>/dynamics`, next to the existing analytics endpoint. It also fixes
`simulation_analytics.py`'s missing comment and repost edges by joining on the trace rather than the JSONL.

| LLM cost | Effort | Validation |
|---|---|---|
| 0 | M | Unit tests on the example DBs. Reproduce Section 2's numbers (51 roots, 18 derived posts, depth 1, 35 blind activations) |

#### A2. Run health card (validity diagnostics)

*What.* A one-screen traffic-light card per run that says whether the run is fit to forecast from.

| Check | Statistic | Example run |
|---|---|---|
| Blind activations | share of activations without a successful refresh | 46%, red |
| Effective participation | distinct acting agents / N; agents never active | 52/74, 47/74; 23 inactive |
| Action mix | likes : posts; `do_nothing` share; compared with reference ratios | 0 likes on Twitter, red |
| Feed degeneracy | k-occurrence Gini of rec slots; share of slots per root | 57% one root, red |
| Horizon coverage | simulated hours ÷ question horizon; scheduled events injected? | 10 h ÷ 336 h; 0 of 3 events, red |
| Clock sanity | platform time span ÷ simulated span | Reddit 2.75 h ÷ 10 h |
| Persona diversity | MBTI entropy; mean pairwise cosine of persona embeddings; entity-type mix; share of "public" agents | 50/74 ISTJ; 0 public agents |
| Logging integrity | duplicated seed posts; comments without parent | 22; 44 |
| Token use | tokens per activation, per run (from camel responses, once logged) | not logged |

*Plugs into.* Same endpoint as A1. Shown as a banner on the Analytics page and the report page.

| LLM cost | Effort | Validation |
|---|---|---|
| 0 (persona embeddings only) | S–M | Each red light must be traceable to a code cause in Section 3 |

#### A3. Cascade structure: size, depth, breadth, structural virality, branching

*Maths.* For a tree $T$ with $n$ nodes:
- size $n$;
- depth $d=\max$ node depth;
- maximum breadth $b=\max_k|\{v:\text{depth}(v)=k\}|$.

Structural virality (Goel et al. 2016) is the mean pairwise distance:

$$\nu(T)=\frac{1}{n(n-1)}\sum_{i\ne j}d_{ij}=\frac{2W(T)}{n(n-1)},\qquad W(T)=\sum_{e\in T}s_e\,(n-s_e),$$

where $s_e$ is the size of the subtree below edge $e$. This gives an $O(n)$ algorithm from one post-order pass. A star
has $\nu=2(n-1)/n<2$; long chains have large $\nu$.

Branching factor: $\hat m=\#\text{derived}/\#\text{posts}$, per generation $\hat m_g$. For a Galton–Watson process with
mean $m<1$, the expected total size is $1/(1-m)$. That gives 1.35 for the example run, matching the observed mean tree
size of 69/51 = 1.35.

Time-varying reproduction number (Cori et al. 2013):

$$R_t=\frac{I_t}{\sum_{s\ge1}I_{t-s}w_s},$$

with $I_t$ = derived posts in round $t$ and $w$ = the empirical parent→child lag distribution from A1.

*Interpretation for users.*
- $\hat m<1$: "conversations die out".
- $\nu$ close to 2: "broadcast, not word of mouth".
- Goel et al. 2016 found popularity is driven mostly by the largest single broadcast, with size and virality only
  weakly correlated. Most real cascades are tiny: 73–95% are the seed alone (Goel, Watts & Goldstein 2012).

These give stylised-fact targets for B3.

| LLM cost | Effort | Validation |
|---|---|---|
| 0 | S | Hand-check on the example trees. Compare distributions with the stylised facts above |

#### A4. Exposure funnel: separating "seen a lot" from "liked a lot"

*Maths.* For post $j$: impressions $N^{\text{imp}}_j$ from $\mathcal E$, engagements $N^{\text{eng}}_j$, and conversion
$c_j=N^{\text{eng}}_j/N^{\text{imp}}_j$. Shrink $c_j$ with a beta-binomial:

$$\hat c_j=\frac{N^{\text{eng}}_j+\alpha}{N^{\text{imp}}_j+\alpha+\beta}$$

with $\alpha,\beta$ fitted across posts by method of moments. Decompose:

$$\log N^{\text{eng}}_j=\log N^{\text{imp}}_j+\log c_j\ \Rightarrow\ \operatorname{Var}\log N^{\text{eng}}=\operatorname{Var}\log N^{\text{imp}}+\operatorname{Var}\log c+2\operatorname{Cov}.$$

The share of variance from impressions is the recommender's share of "virality"; the share from conversion is the
content's. Concentration should also be split: the impression Gini (recommender, 0.86 here) versus the conversion Gini
(agents).

*Exposure–response curve* (Romero et al. 2011). For agent $i$ and a narrative or root $q$, let $k$ be the number of
distinct exposures to $q$ before $i$ adopts it (shares, quotes or comments). Estimate
$p(k)=P(\text{adopt after exposure }k{+}1\mid k\text{ exposures, not yet adopted})$. A $p(k)$ that rises for $k\ge2$
indicates complex contagion. *Position effect:* a logistic regression of engagement on feed position with post fixed
effects. This tests for LLM order bias.

| LLM cost | Effort | Validation |
|---|---|---|
| 0 | S–M | Sanity: engaged posts must be in the current feed (18/18 and 62/62 in the example) |

#### A5. Stance and opinion trajectories, polarization, and interaction value-added

*Targets.* An LLM drafts 3–6 propositions $q_1..q_m$ from `simulation_requirement` (for example "Huang's exit damages
Nvidia's prospects" or "Export enforcement was too lax"). The user edits and freezes them.

*Measurement.*
- A cheap LLM judge labels each post, quote and comment with stance $s\in\{-1,0,+1\}$ toward each $q$, plus intensity
  in $[-1,1]$ and confidence. Inputs are batched about 20 per call.
- Validate on 100 hand-labelled texts using the SemEval-2016 Task 6 metric $F_{\text{avg}}=(F_{\text{favor}}
  +F_{\text{against}})/2$ (Mohammad et al. 2016). Cross-check a second model for agreement.
- Label the persona text too, giving a prior $x_i(0)$.
- Agent opinion is an exponentially weighted average of the agent's own stances:
  $x_i(t)=(1-\eta)x_i(t^-)+\eta\,s$. Alternatively keep Beta counts to get a posterior with uncertainty.

*Population indices per round.*
- Mean and variance of $x$.
- Esteban–Ray polarization $P_{ER}=K\sum_i\sum_j\pi_i^{1+\alpha}\pi_j|y_i-y_j|$ on binned opinions (Esteban & Ray
  1994).
- Morales et al. 2015: $\mu=(1-\Delta A)\,d$, where $\Delta A$ is the imbalance between the poles and $d$ is the
  distance between their centres.
- On the interaction or exposure graph:
  - the E-I index $(E-I)/(E+I)$ of cross-stance versus same-stance ties (Krackhardt & Stern 1988; used as an echo-chamber
    measure by Törnberg et al. 2023 and Larooij & Törnberg 2025);
  - Musco et al. 2018's polarization $P=\sum_u\bar z_u^2$ and disagreement $D=\sum_{(u,v)}w_{uv}(z_u-z_v)^2$;
  - Guerra et al. 2013's boundary polarization;
  - Garimella et al. 2018's random-walk controversy score $\text{RWC}=P_{XX}P_{YY}-P_{XY}P_{YX}$, for runs large
    enough to be meaningful.

*Fitting classical opinion dynamics to LLM agents (explanation).* For each agent observed at least twice, regress

$$\Delta x_i=\beta_0+\beta_1\big(\bar s^{\text{exp}}_i-x_i\big)+\beta_2\big(\bar s^{\text{exp}}_i-x_i\big)\mathbb 1\big[|\bar s^{\text{exp}}_i-x_i|>\varepsilon\big]+\epsilon,$$

where $\bar s^{\text{exp}}_i$ is the mean stance of what $i$ was shown in between. Reading the coefficients:
- $\beta_1$ is an effective DeGroot or Friedkin–Johnsen susceptibility, the weight placed on others (DeGroot 1974;
  Friedkin & Johnsen 1990).
- A negative $\beta_2$ means bounded confidence (Deffuant et al. 2000; Hegselmann & Krause 2002). A strongly negative
  one means backfire (compare Bail et al. 2018).
- A $\beta_0$ that moves everyone toward the official position is the consensus drift of Chuang et al. 2024.

This tells the owner in classical terms "how persuadable the simulated crowd is".

*Interaction value-added.* $R^2$ of final $x_i(T)$ on the persona prior $x_i(0)$. If $R^2\approx1$, the social
simulation added little beyond the LLM's view of each entity. That is a central fact for interpreting any forecast.

| LLM cost | Effort | Validation |
|---|---|---|
| About 145 texts per run → about 8 batched calls → about 30–50k tokens, roughly 5% of a run | M | Labelled sample F1; inter-model agreement; indices tested on synthetic opinion sets with known polarization |

#### A6. Attention dynamics: half-lives and infectiousness

*Maths.*
- **Per-root counts.** Let $n_j(t)$ be the engagement count of root $j$ in round $t$. Fit a pooled Poisson GLM
  $n_j(t)\sim\text{Poisson}\big(A_j\,g(t-t_j;\theta)\big)$. Compare an exponential kernel $g=e^{-(t-t_j)/\tau}$
  (half-life $\tau\ln2$) with a power-law kernel $g=(t-t_j+c)^{-(1+\theta)}$ (Crane & Sornette 2008; Wu & Huberman 2007,
  whose Digg novelty half-life was 69 min). Choose by AIC; data is sparse, so pool across posts.
- **Infectiousness** in SEISMIC form (Zhao et al. 2015): $\hat p_t=R_t/N^e_t$, with
  $N^e_t=\sum_i n_i\int_{t_i}^{t}\phi(s-t_i)\,ds$. Here $n_i$ can be the *actual* impressions from A1 instead of
  follower counts, which SEISMIC has to use as a proxy.
- **Run-level branching ratio** $n^*$, the Hawkes branching factor (Hawkes 1971; Rizoiu et al. 2017). The process is
  subcritical if $n^*<1$, with expected cluster size $1/(1-n^*)$.
- **Topic attention.** Track the share of posts per round matching each `hot_topic` or embedding cluster. This becomes
  the "attention river" in Section 6.

*Caveat.* Until B1 fixes the clocks, half-lives are in rounds, not hours.

| LLM cost | Effort | Validation |
|---|---|---|
| 0 | S–M | Recover known parameters from synthetic Hawkes data before trusting fits on real runs |

#### A7. Concentration and inequality

Compute the Gini coefficient, top-$k$ share and Herfindahl–Hirschman index for:
- impressions, engagement and followers per agent and per post;
- the k-occurrence distribution of rec slots (hubness; Radovanović et al. 2010).

Compare with stylised facts:
- 10% of accounts produce 80% of posts (Pew 2019);
- social influence raises inequality (Salganik et al. 2006).

Use A4 to say whether concentration came from the recommender or from agents. Cost 0, effort S.

#### A8. Quantified appendix and plain-language explainers

Append a deterministic section to the report: numbers and charts from A1–A7, generated from templates and not by the
ReportAgent. The LLM-written report stays byte-identical to upstream behaviour. Its content is designed in Section 6.
Cost 0 (or one cheap call to phrase captions), effort S–M plus UI.

### Group B: model changes (predictions change)

Every B item must pass the backtest in Section 5 before becoming the default. Each should ship behind a config flag so
upstream-identical runs stay possible.

#### B1. Correctness fixes: make the engine do what its configuration says

All of these go through the `Platform` subclass and the runner, not site-packages.

| Fix | Change |
|---|---|
| D1 quote crash | In the `_add_comments_to_posts` override, read `num_reports` for quote rows; serialise each post in its own try block so one bad row cannot blank a feed |
| D2 recency | Recompute recency every update: $\rho_j(t)=2^{-(t-t_j)/h_{1/2}}$ with $t$ in simulated minutes; delete the global `date_score` list |
| D3 quotes | Embed quote rows as `quote_content` (plus a short original excerpt); at most one item per root in a feed; exclude the user's own posts and already-seen posts (or decay them) |
| D4 Reddit | Use the hot order: the feed is the top-$k$ unseen posts by hot score, with ε-exploration (for example ε = 0.2 uniform). Optionally personalise by subreddit or topic |
| D5 clocks | One clock for both platforms: $t=t_0+r\Delta$ minutes, advanced every round including empty ones |
| D6 activation | Scale the per-agent probability rather than the cap: $P(i\in S_r)=\mathbb 1[h_r\in H_i]\min(1,\kappa\,a_i\,\mu(h_r))$, with all five configured multipliers and $\kappa$ solved so that $\mathbb E|S_r|$ equals the configured target. Seed `random`, `numpy` and `torch` from a run seed stored in `run_state.json` |
| D7 seed posts | Use lists for Twitter as Reddit does |
| D8 dead fields | Wire `recency/popularity/relevance_weight` into B3's ranker. Remove or wire `stance`, `sentiment_bias` and `influence_weight` (B7). Delete the rest from the config prompt |
| D9 logging | Start `last_rowid` after the seed step; log `reposted_id`; for comments, join `comment.post_id`; persist refresh traces (exposures) |
| D10 prompt | Neutral instruction: "Choose what you would realistically do now. Most real users mostly read, sometimes like, and rarely post." Report the action mix in A2 |

| LLM cost | Effort | Validation |
|---|---|---|
| Roughly neutral. Blind agents now see feeds, which adds 0.3–1k tokens per activation | S–M (2–3 days) | A2 health card from all red to green on a rerun of the example config. Regression tests on fixture DBs. Backtest (Section 5) to confirm accuracy does not regress |

#### B2. Seeded ensembles with prediction intervals

*Maths.* Run $K$ replicas with seeds $\sigma_1..\sigma_K$. Provider sampling adds further noise that cannot be seeded.
Define outcome functionals $Y=g(\text{run})$, for example:
- final share of content against $q$ (from A5);
- the round of peak attention for a topic;
- whether narrative $N$ ends with the largest attention share;
- the maximum cascade size;
- the identity of the top influencer.

Estimates:

$$\hat P(E)=\frac1K\sum_k\mathbb 1[E_k]\ \text{(Jeffreys or Wilson interval)},\qquad \hat Q_Y(\alpha)=\text{empirical quantiles}.$$

The binomial standard error is $\sqrt{p(1-p)/K}$: about ±0.11 at $K=20$ and ±0.07 at $K=50$ for $p=0.5$. Use
sequential stopping: keep adding replicas until the 90% interval half-width falls below a target δ or $K_{\max}$ is
reached.

*Nested design for "luck versus set-up".* Use $M$ configurations (persona regeneration, prompt paraphrase, model
mixture from B7) × $K$ seeds:

$$\operatorname{Var}(Y)=\underbrace{\mathbb E[\operatorname{Var}(Y\mid c)]}_{\text{luck}}+\underbrace{\operatorname{Var}(\mathbb E[Y\mid c])}_{\text{set-up}}.$$

If set-up variance dominates, the forecast depends on how personas were written, which users must be told.

*What the report receives.* The ensemble summary, a medoid run (the replica closest to the ensemble median on the key
$Y$s) as the narrative, and one contrasting tail run. Not a single arbitrary run.

*Plugs into.* `simulation_runner.py` launches replicas as separate simulation directories (`sim_x/rep_k/`). The
`simulation_manager` holds a parent "ensemble" record. Analytics A1–A7 aggregate across replicas.

*LLM cost.* $K\times$ the simulation cost. At about 0.5–1M input tokens per 10-round run, $K=20$ is about 10–20M
tokens. Personas and config are reused unless the nested design is on. Persona generation (74 personas of about 2,000
words each) is itself a large share of output tokens. The persona plus tool schemas form a stable prefix, so check
whether the provider's prompt caching can apply through the OpenAI-compatible path before assuming savings.

*Effort.* M (4–6 days).

*Validation.* Calibration of $\hat P$ and the intervals in the backtest (Section 5): reliability, PIT, interval
coverage. Check spread against skill (Leutbecher & Palmer 2008): RMS error of the ensemble mean should track ensemble
spread after the $(K+1)/(K-1)$ correction, assessed in bins of predicted spread.

#### B3. A social graph and an honest recommender, with algorithm variants

*Initial follow graph $G_0$.* Use the knowledge graph Hivemind already has. Zep edges between entities mean
relationships such as regulates, covers, employs or competes with:

$$P(i\to j)=\sigma\big(\beta_0+\beta_1\,\mathbb 1[\text{KG edge }ij]+\beta_2\,\mathbb 1[\text{type}_i=\text{type}_j]+\beta_3\log(\text{influence}_j)\big)$$

This is the first real use of `influence_weight`. The $\beta$s are tuned so in-degree is heavy-tailed. Media and
officials should be widely followed.

*Ranker* (implements the `PlatformConfig` weights that already exist):

$$\text{score}_{ij}=w_{\text{rel}}\cos(u_i,v_j)+w_{\text{pop}}\log(1+E_j)+w_{\text{rec}}\,2^{-(t-t_j)/h_{1/2}}+w_{\text{net}}\mathbb 1[\text{author}(j)\in F_i]+w_{\text{soc}}\,\big|\{k\in F_i:k\text{ engaged }j\}\big|$$

Sample a feed of size $k$ with Gumbel-top-$k$, which is Plackett–Luce sampling:
$\tilde s_{ij}=\text{score}_{ij}/T+G_{ij}$, $G\sim\text{Gumbel}(0,1)$. $T$ sets exploration. Apply the dedupe and
exclusions from B1. **Reposts and quotes enter the followers' candidate sets.** This is the mechanism that makes
multi-level cascades possible. Consider replacing TwHIN `pooler_output` with mean-pooled sentence embeddings and check
hubness in A7.

*Variants as a sensitivity analysis.* Chronological ($w_{\text{rec}}$ only), engagement ($w_{\text{pop}}$), similarity
($w_{\text{rel}}$), bridging (rank by cross-stance engagement, as in Törnberg et al. 2023) and random. Run B2 ensembles
per variant and report $\Delta Y$ with intervals. Real-world evidence that the ranker matters:
- Huszár et al. 2022 measured algorithmic amplification against a reverse-chronological control.
- Guess et al. 2023 found a chronological feed changed exposure and engagement substantially but not measured
  polarization over 3 months.
- Larooij & Törnberg 2025 found most simulated interventions had only modest effects.

The doc should state honestly that a forecast which flips with the ranker is a ranker-dependent forecast.

| LLM cost | Effort | Validation |
|---|---|---|
| About 0 extra; embedding compute only. Feeds of k = 5–10 posts add about 1–2k tokens per activation | M–L (1–2 weeks) | Stylised-facts scorecard (Section 5.6): heavy-tailed cascade sizes; most cascades singletons; occasional depth ≥ 2; low but non-zero ν; concentration comparable to Pew. Replicate OASIS's Twitter15/16 scale, depth and breadth normalized-RMSE benchmark |

#### B4. Calibrated activation and a two-tier action economy

*Activation.* Each agent gets a base rate $\mu_i$, heavy-tailed (lognormal by entity type) and calibrated so that about
10% of accounts produce about 80% of posts (Pew 2019). Apply a diurnal profile $d(h)$ and self-excitation from
notifications:

$$\lambda_i(t)=\mu_i\,d(h_t)+\sum_{k:\,t_k<t}\alpha_{\text{type}(k)}\,g(t-t_k),\qquad P(i\text{ active in round }r)=1-\exp\!\Big(-\int_{\text{round }r}\lambda_i\Big),$$

where the events $k$ are replies, quotes, likes and follows directed at $i$ (Hawkes 1971). This plugs into
`get_active_agents_for_round` (`run_parallel_simulation.py:1040`).

*Two-tier policy.*
- **Tier 0 (no LLM)** handles passive reading and likes:
  $P(\text{like}_{ij})=\sigma\big(\gamma_0+\gamma_1\cos(\text{persona}_i,v_j)+\gamma_2(1-|s_j-x_i|)+\gamma_3\log(1+E_j)\big)$.
  It is calibrated to platform base rates and executed as `ManualAction(LIKE_POST)`.
- **Tier 1 (LLM)** is invoked only when Tier 0 draws "would write". This restores realistic action mixes, gives the
  popularity terms real signal, and cuts LLM calls.

| LLM cost | Effort | Validation |
|---|---|---|
| Lower: fewer LLM calls per active agent-round, likely 2–5× fewer for the same activity level (to be measured) | M–L | Activity Gini, inter-event time distributions and action mix against reference data; backtest |

#### B5. A representative population: public agents and a hybrid crowd

*Segments.* Add "public" agents for segments the question names, such as retail investors, employees and voters by
lean, each with a weight $w_g$ equal to its population share. Personas come from segment templates rather than
knowledge-graph entities.

*Hybrid crowd*, following HiSim's design (Mou et al. 2024): about 50–100 LLM core agents plus $N_c$ rule-based crowd
agents with opinions $x\in[-1,1]$ updated by bounded-confidence Friedkin–Johnsen:

$$x_i(t+1)=\lambda_i\!\!\sum_{j\in F_i(t),\,|s_j-x_i|<\varepsilon_i}\!\!\tilde W_{ij}\,s_j+(1-\lambda_i)\,x_i(0)$$

- $\tilde W$ = exposure weights renormalised over the posts that pass the confidence filter.
- $s_j$ = the post stance from A5.
- If no post passes, $x_i$ is unchanged.

Optionally add biased assimilation (Dandekar et al. 2013). Crowd agents engage with probability as in Tier 0, and their
likes and reposts feed back into popularity. The crowd amplifies or ignores LLM content at scale.

*Parameters* $\lambda,\varepsilon$ are uncertain. Draw them from priors per replica so the uncertainty propagates
through B2, and fit them in the backtest. *Output:* a population-weighted opinion distribution with intervals, which is
what "public reaction" questions need.

| LLM cost | Effort | Validation |
|---|---|---|
| Crowd is about free; core unchanged | L | Compare with polls after events where available; backtest |

#### B6. Explicit belief state, scheduled events, and what-if interventions

*Belief state.* After each activation, update a compact per-proposition view, either the A5 classification or a
one-line self-report, and include it in the next prompt. Replace the unbounded transcript with retrieval scored as in
Park et al. 2023, $\text{score}=\alpha_1\text{recency}+\alpha_2\text{importance}+\alpha_3\text{relevance}$, under a
token budget. This makes beliefs persistent and inspectable, and stops quadratic cost growth.

*Scheduled events.* Fill `EventConfig.scheduled_events` from the requirement's timeline, such as earnings or a
government visit. The runner injects them as official or media posts in the matching round. Combined with B1's clock,
a two-week question then gets a two-week simulation, or an explicitly time-compressed one.

*Interventions.* For a what-if such as "Nvidia issues a statement in round 3", run paired ensembles with common random
numbers (the same seeds):

$$\hat\Delta=\frac1K\sum_k\big(Y_k^{\text{treat}}-Y_k^{\text{ctrl}}\big),$$

with a CI from a paired bootstrap. Common random numbers shrink the variance of $\hat\Delta$ but do not remove the
unseeded LLM noise.

| LLM cost | Effort | Validation |
|---|---|---|
| 2K runs per what-if; belief summaries are about 0 extra | M | Backtest on events with known follow-up events; check $\hat\Delta$ signs against observed reactions |

#### B7. LLM-bias controls and model mixing

- **Model mixing.** `SocialAgent` already uses `scheduling_strategy='random_model'` and accepts a list of backends
  (`agent.py:106-111`). Assign each agent a model from a pool of families, which reduces single-model monoculture. B2's
  nested design measures between-model variance.
- **Persona diversity gate.** Regenerate when A2 flags degeneracy, such as 50/74 ISTJ or high mean persona similarity.
  Optionally put the config's `stance` into the persona so it is no longer decorative, and test whether that improves
  backtest scores.
- **Built-in bias probes.**
  - Herding: seed matched posts with +1 or −1 initial votes, as in Muchnik et al. 2013 and OASIS, and compare effect
    sizes with the human results.
  - Consensus drift: a neutral-exposure control (Chuang et al. 2024).
  - Opposition voicing: the stance mix compared with persona priors (HiSim).

  If agents herd more than humans, hide or perturb social counts. "Hide social statistics" is one of Larooij &
  Törnberg's interventions.
- **Source cues.** Show display names, and optionally account type, in feeds instead of `User N`.

| LLM cost | Effort | Validation |
|---|---|---|
| Probes cost a few small runs; model mixing depends on the pool | M | Probe effect sizes against human references; backtest |

#### B8. A forecast layer: explicit questions, outside view, calibrated pooling

1. **Questions.** Turn the requirement into forecast questions $q_k$ with resolution criteria and a horizon. An LLM
   drafts them and the user confirms.
2. **Mapping.** Map each $q_k$ either to a simulation functional $g_k$ (B2) or to a structured panel interview at the
   end of every replica: fixed questionnaire, fixed agent sample, `interview_record=False`.
3. **Prior.** Obtain an outside-view prior $p^{\text{prior}}_k$ from the same model given only the seed documents and
   no simulation. This is also the key baseline in Section 5.
4. **Combine with a recalibration fitted on backtests:**

   $$\operatorname{logit}p_k=a+b\,\operatorname{logit}\hat p^{\text{sim}}_k+c\,\operatorname{logit}p^{\text{prior}}_k.$$

   $b\approx0$ means the simulation adds nothing. $b+c>1$ means aggregation should extremize (Baron et al. 2014).
5. **Report.** Show the probability with its interval, "in 37 of 50 simulated worlds...", the drivers (top cascades and
   agents from A3–A5), and the prior.
6. **Provenance.** Tag facts as seed or simulated; the episode text already carries `[platform round N]`. Report
   abstention rates from `DO_NOTHING`.

| LLM cost | Effort | Validation |
|---|---|---|
| A few calls per report | M | This is what Section 5 scores |

### 4.1 Overall ranking

| Rank | ID | Group | Value | Effort | LLM cost | Depends on |
|---|---|---|---|---|---|---|
| 1 | B1 correctness fixes | B | Removes artefacts that currently dominate dynamics | S–M | ≈0 | — |
| 2 | A1+A2+A3 trace store, health card, cascades | A | Makes spread visible and run quality explicit | M | 0 | — |
| 3 | B2 ensembles + intervals (+ B8 extraction) | B | Turns a story into a scoreable distribution | M | K× | B1 (seeding) |
| 4 | A5 stance, polarization, interaction value-added | A | Measures opinions; tests whether interaction matters | M | ~5% | A1 |
| 5 | B3 graph + ranker + variants | B | Enables real diffusion; algorithm sensitivity | M–L | ≈0 | B1 |
| 6 | B8 forecast layer and calibration | B | Outside view plus learned pooling | M | small | B2, backtest |
| 7 | A4 exposure funnel | A | "Seen a lot or liked a lot" | S–M | 0 | A1 |
| 8 | B4 activation + two-tier actions | B | Realistic activity; saves tokens | M–L | lower | B1 |
| 9 | B5 public agents + hybrid crowd | B | Representativeness for population questions | L | ≈0 | A5, B2 |
| 10 | B6 beliefs, scheduled events, what-ifs | B | Horizon fit; counterfactual explanations | M | 2K per what-if | B2 |
| 11 | A6 attention fits | A | Half-lives, criticality | S–M | 0 | A1, B1 clocks |
| 12 | A7 concentration and hubness | A | Who dominates, and why | S | 0 | A1 |
| 13 | B7 bias controls, model mixing | B | Reduces known LLM artefacts | M | varies | A5 |
| 14 | A8 quantified appendix | A | Delivery vehicle for the above | S–M | ~0 | A1–A7 |

---

## 5. Evaluation and backtesting protocol

The aim is to show, with proper scoring rules and paired tests, whether a change improves forecasts of real outcomes,
and whether the simulation beats simply asking the LLM.

### 5.1 What gets scored

1. **Primary: real-world outcome questions.** These are the questions users actually ask.
   - Binary: "Will X be named CEO by date D?"
   - Numeric: "Nvidia close on D".
   - Categorical: "which narrative dominates coverage".
2. **Secondary: discourse outcomes.** Where data access allows: narrative share, stance share and top accounts in real
   social-media or news data over the horizon.
3. **Mechanism checks.** The stylised facts in Section 5.6. These are necessary but not sufficient.

### 5.2 Event set construction

- **Size.** About 60–100 past events across domains: corporate, political, product launches, scandals. Each has 3–8
  questions written and **frozen before any run**, with resolution sources. Include "nothing happens" and status-quo
  questions to avoid selecting dramatic outcomes.
- **As-of snapshots.** Seed corpora contain only documents published before $t_0$, checked by publication date.
- **Leakage controls** (Paleka et al. 2025; Glasserman & Lin 2023):
  - Prefer events after the simulation model's training cutoff.
  - For older events, anonymise entities and dates and test leakage directly by asking the model the question with no
    context. Drop events it answers confidently and correctly.
  - Disable web or tool access during runs.
  - Record model ids and package versions.
- **Halawi et al. 2024's approach.** They kept the evaluation clean by testing only on questions published after the
  models' knowledge cutoffs and by limiting retrieval dates to each question's open window. ForecastBench (Karger et al.
  2025) avoids leakage by construction, using only unresolved questions. A rolling live benchmark of that kind is the
  cleanest long-run option.

### 5.3 Arms

Arms are compared on identical questions and seed documents.

| Arm | Description |
|---|---|
| A0 | Base rate or climatology per question class |
| A1 | **LLM-only**: same model, same seed documents, direct probabilistic forecast (the outside-view prior of B8) |
| A2 | Current Hivemind single run, plus a fixed report-to-probability extractor (an LLM reads the report and outputs probabilities, with the same extractor for every arm) |
| A3 | Hivemind with B1 fixes, single run |
| A4 | Ensemble (B2) |
| A5+ | One arm per further B change, ablated one at a time |
| H | Human crowd, where questions overlap with public forecasting platforms (optional) |

The A1 versus A2–A4 comparison is the most important test in the whole programme. If the simulation does not beat
asking the LLM directly, the simulation is useful for explanation but not for accuracy.

### 5.4 Scoring

Brier score and log score (Brier 1950; Gneiting & Raftery 2007):

$$\text{BS}=\frac1N\sum_k(p_k-o_k)^2,\qquad \text{LS}=-\frac1N\sum_k\log p_k(o_k)\ \ (\text{clip }p\text{ to }[0.01,0.99]).$$

For numeric targets with ensemble members $y_1..y_K$, use the continuous ranked probability score (Matheson & Winkler
1976; Gneiting & Raftery 2007):

$$\text{CRPS}=\frac1K\sum_k|y_k-y|-\frac1{2K^2}\sum_{k,l}|y_k-y_l|.$$

For a central $(1-\alpha)$ interval $[l,u]$, use the interval score:

$$(u-l)+\tfrac{2}{\alpha}(l-y)\mathbb 1[y<l]+\tfrac{2}{\alpha}(y-u)\mathbb 1[y>u].$$

Diagnostics:
- the Murphy (1973) decomposition $\text{BS}=\text{REL}-\text{RES}+\text{UNC}$;
- reliability diagrams;
- PIT histograms;
- sharpness. The target is maximal sharpness subject to calibration (Gneiting, Balabdaoui & Raftery 2007).

Report skill against the baseline as $\text{SS}=1-\text{BS}/\text{BS}_{\text{A0}}$.

### 5.5 Comparing arms

- **Paired differences.** Compute per-question differences $d_k=S^{X}_k-S^{Y}_k$. Average to the **event** level first,
  because questions within an event are correlated. Then use a cluster bootstrap CI and a Diebold–Mariano-style test on
  event means (Diebold & Mariano 1995).
- **Pre-registration.** Fix one primary metric (Brier on binary questions) and one primary contrast per change. Apply
  Holm correction across arms.
- **Sample size.**
  $n\approx\big((z_{1-\alpha/2}+z_{1-\beta})\,\sigma_d/\delta\big)^2$ events. With a pilot estimate
  $\sigma_d\approx0.08$ (a placeholder to measure, not a known value) and $\delta=0.02$, $n\approx125$. Run a pilot of
  about 20 events to estimate $\sigma_d$ before committing.
- **Decision rule.** Ship a B change as the default only if the primary contrast's CI excludes zero in the right
  direction, calibration does not worsen, and no stylised fact regresses.

### 5.6 Mechanism scorecard (per run, cheap, no outcome data needed)

| Stylised fact | Source | Test |
|---|---|---|
| Most cascades are the seed alone; very few exceed a handful of nodes | Goel, Watts & Goldstein 2012 | singleton share within a tolerance band |
| Popularity driven mostly by large broadcasts; structural virality usually low, weakly related to size | Goel et al. 2016 | ν distribution; corr(size, ν) |
| Heavy-tailed activity: about 10% of accounts make about 80% of posts | Pew 2019 | top-decile share of posts |
| Positive herding, negative correction | Muchnik et al. 2013 | herding probe (B7) |
| Social influence raises inequality and unpredictability | Salganik et al. 2006 | Gini and between-replica variance rise when social signals are shown versus hidden |
| Early cascade growth predicts doubling | Cheng et al. 2014 | AUC of "will it double" from the first k shares, within the ensemble |
| Cascade scale, depth and breadth versus Twitter15/16 | OASIS paper | normalized RMSE, compared with OASIS's ~30% |

### 5.7 Ensemble calibration

- Coverage of 50/80/90% intervals.
- Rank histograms of the realised outcome among the ensemble members.
- Spread against skill in bins (Leutbecher & Palmer 2008). Under-dispersion, which is likely given LLM homogeneity,
  shows up as U-shaped rank histograms. The remedies are the nested design (B2) and model mixing (B7).

### 5.8 Reproducibility and cost

- Store per run:
  - seed;
  - model id;
  - package versions (`camel-oasis` 0.2.5, `camel-ai` 0.2.78);
  - every prompt and response;
  - the token counts that A2 adds.
- Budget formula: $\text{cost}\approx\text{events}\times\text{arms}\times K\times\text{tokens per run}$. For example,
  100 events × 3 simulation arms × K = 10 × 1M tokens ≈ 3B input tokens. Start with a 20-event pilot at K = 5 and use
  B4's cheaper action tier to cut costs.

---

## 6. Making it understandable and interactive for ordinary people

Principles, from the uncertainty-communication literature:
- Use natural frequencies rather than bare probabilities. Bayesian reasoning rose from 16% to 46–50% correct in
  Gigerenzer & Hoffrage 1995.
- Offer more than one representation, because understanding depends on numeracy (Spiegelhalter, Pearson & Short 2011).
- Show discrete outcomes rather than error bars: quantile dotplots (Kay et al. 2016) and hypothetical outcome plots
  (Hullman, Resnick & Adar 2015).
- Be honest about uncertainty. In the limited evidence available it does not necessarily harm trust (van der Bles et
  al. 2019).

### 6.1 Views

1. **"50 simulated worlds" headline (B2).**
   - Lead with a frequency: "In 37 of 50 simulated worlds, criticism of the Commerce Department was the largest
     conversation by day 3."
   - Show a quantile dotplot of 20 dots for numeric outcomes.
   - Offer an animated replay of individual worlds (HOP) so users feel the spread.
   - Never show a single run without saying it is one of many possible.
2. **Health badge (A2).** Green, amber or red, with plain reasons: "Most simulated accounts are organisations, not
   ordinary people. Treat 'public mood' conclusions with caution." "40% of simulated users saw an empty feed (engine
   bug); the dynamics are unreliable."
3. **How a post travelled (A1, A3).**
   - A tree picture for each top cascade: the root author, then who passed it on and when.
   - Two plain scores:
     - "Reach": how many accounts saw it.
     - "Word-of-mouth score": structural virality, shown as "broadcast" near 2 and "chain reaction" when higher.
   - Example caption: "This post was seen by 15 accounts because the feed algorithm matched it to their profiles. Nobody
     passed it on, so it spread like a TV broadcast, not like gossip."
4. **Seen versus liked (A4).**
   - A two-bar funnel per post: shown to, then engaged, then passed on.
   - A one-line verdict: "It went far because the feed pushed it", or "it went far because people who saw it acted".
5. **Is the conversation growing or dying? (A3, A6).**
   - A gauge for the branching factor: "each post produces about 0.3 new posts, so threads fizzle".
   - A half-life: "attention halves every N hours".
6. **Opinion river (A5).**
   - A stacked area of for, neutral and against per proposition over time, with ensemble bands.
   - A polarization meter: "how split, and how far apart".
   - The interaction value-added line: "Most agents ended where their persona started: this forecast mostly reflects how
     the AI imagines each organisation, not a debate."
7. **Why did this account say that?**
   - For any post, show exactly what the agent saw in its feed at that moment (from the refresh trace) and its persona
     summary.
   - This is full transparency that real platforms cannot offer, and the most direct explanation of "how the effect
     happened".
8. **What if? (B6).**
   - A form along the lines of "What if [actor] does [action] in [round]?".
   - It shows a cost estimate in tokens before running.
   - It returns "Δ = +12 points (80% range +4 to +19) across 20 paired worlds".
9. **Compare algorithms (B3).** Toggle chronological, engagement or bridging and see whether the headline survives.
   "The forecast holds under all three feed types" is a strong statement. "It flips" is an important warning.
10. **Glossary on hover.** Each term gets one sentence:
    - *Branching factor*: how many new posts one post triggers.
    - *Structural virality*: chain reaction versus broadcast.
    - *Calibrated*: when we say 70%, it happens about 7 times in 10.

### 6.2 Wording rules for the report

- Always pair a probability with a frequency and a range.
- Separate what the seed documents say from what simulated agents did. Label quotes as simulated.
- State the horizon actually simulated, for example "10 simulated hours", next to any claim about "days".
- Show the outside-view prior (B8) next to the simulation's estimate, and say which way the simulation moved it.

---

## 7. References

These were checked against Crossref, publisher pages, arXiv, PubMed or the original code. Partial verifications are
noted in brackets.

**Cascades and diffusion**
- Kempe, D., Kleinberg, J., Tardos, É. (2003). Maximizing the spread of influence through a social network. *KDD '03*, 137–146. doi:10.1145/956750.956769
- Granovetter, M. (1978). Threshold models of collective behavior. *American Journal of Sociology* 83(6):1420–1443. doi:10.1086/226707
- Goldenberg, J., Libai, B., Muller, E. (2001). Talk of the network: A complex systems look at the underlying process of word-of-mouth. *Marketing Letters* 12(3):211–223. doi:10.1023/A:1011122126881
- Goel, S., Anderson, A., Hofman, J., Watts, D.J. (2016). The structural virality of online diffusion. *Management Science* 62(1):180–196. doi:10.1287/mnsc.2015.2158
- Goel, S., Watts, D.J., Goldstein, D.G. (2012). The structure of online diffusion networks. *EC '12*, 623–638. doi:10.1145/2229012.2229058
- Cheng, J., Adamic, L., Dow, P.A., Kleinberg, J., Leskovec, J. (2014). Can cascades be predicted? *WWW '14*, 925–936. doi:10.1145/2566486.2567997
- Vosoughi, S., Roy, D., Aral, S. (2018). The spread of true and false news online. *Science* 359(6380):1146–1151. doi:10.1126/science.aap9559
- Salganik, M.J., Dodds, P.S., Watts, D.J. (2006). Experimental study of inequality and unpredictability in an artificial cultural market. *Science* 311(5762):854–856. doi:10.1126/science.1121066
- Martin, T., Hofman, J.M., Sharma, A., Anderson, A., Watts, D.J. (2016). Exploring limits to prediction in complex social systems. *WWW '16*, 683–694. doi:10.1145/2872427.2883001
- Hofman, J.M., Sharma, A., Watts, D.J. (2017). Prediction and explanation in social systems. *Science* 355(6324):486–488. doi:10.1126/science.aal3856
- Centola, D., Macy, M. (2007). Complex contagions and the weakness of long ties. *American Journal of Sociology* 113(3):702–734. doi:10.1086/521848
- Centola, D. (2010). The spread of behavior in an online social network experiment. *Science* 329(5996):1194–1197. doi:10.1126/science.1185231
- Romero, D.M., Meeder, B., Kleinberg, J. (2011). Differences in the mechanics of information diffusion across topics. *WWW '11*, 695–704. doi:10.1145/1963405.1963503
- Weng, L., Flammini, A., Vespignani, A., Menczer, F. (2012). Competition among memes in a world with limited attention. *Scientific Reports* 2:335. doi:10.1038/srep00335
- Gomez-Rodriguez, M., Leskovec, J., Krause, A. (2010). Inferring networks of diffusion and influence. *KDD '10*, 1019–1028. doi:10.1145/1835804.1835933
- Muchnik, L., Aral, S., Taylor, S.J. (2013). Social influence bias: A randomized experiment. *Science* 341(6146):647–651. doi:10.1126/science.1240466

**Point processes and popularity**
- Hawkes, A.G. (1971). Spectra of some self-exciting and mutually exciting point processes. *Biometrika* 58(1):83–90. doi:10.1093/biomet/58.1.83
- Zhao, Q., Erdogdu, M.A., He, H.Y., Rajaraman, A., Leskovec, J. (2015). SEISMIC: A self-exciting point process model for predicting tweet popularity. *KDD '15*, 1513–1522. doi:10.1145/2783258.2783401
- Rizoiu, M.-A., Xie, L., Sanner, S., Cebrian, M., Yu, H., Van Hentenryck, P. (2017). Expecting to be HIP: Hawkes intensity processes for social media popularity. *WWW '17*, 735–744. doi:10.1145/3038912.3052650 [exact definition of the scaling constant C not verified]
- Rizoiu, M.-A., Lee, Y., Mishra, S., Xie, L. (2017). Hawkes processes for events in social media. In *Frontiers of Multimedia Research*, ACM Books, 191–218. doi:10.1145/3122865.3122874
- Crane, R., Sornette, D. (2008). Robust dynamic classes revealed by measuring the response function of a social system. *PNAS* 105(41):15649–15653. doi:10.1073/pnas.0803685105
- Wu, F., Huberman, B.A. (2007). Novelty and collective attention. *PNAS* 104(45):17599–17601. doi:10.1073/pnas.0704916104
- Szabo, G., Huberman, B.A. (2010). Predicting the popularity of online content. *Communications of the ACM* 53(8):80–88. doi:10.1145/1787234.1787254
- Cori, A., Ferguson, N.M., Fraser, C., Cauchemez, S. (2013). A new framework and software to estimate time-varying reproduction numbers during epidemics. *American Journal of Epidemiology* 178(9):1505–1512. doi:10.1093/aje/kwt133
- Barabási, A.-L. (2005). The origin of bursts and heavy tails in human dynamics. *Nature* 435:207–211. doi:10.1038/nature03459 [the power-law interpretation is disputed; see arXiv physics/0510216]

**Opinion dynamics**
- DeGroot, M.H. (1974). Reaching a consensus. *JASA* 69(345):118–121. doi:10.1080/01621459.1974.10480137
- Friedkin, N.E., Johnsen, E.C. (1990). Social influence and opinions. *Journal of Mathematical Sociology* 15(3–4):193–206. doi:10.1080/0022250X.1990.9990069 [the diagonal-susceptibility matrix notation used here is the later standard form; not checked against the 1990 text]
- Deffuant, G., Neau, D., Amblard, F., Weisbuch, G. (2000). Mixing beliefs among interacting agents. *Advances in Complex Systems* 3(1–4):87–98. doi:10.1142/S0219525900000078
- Hegselmann, R., Krause, U. (2002). Opinion dynamics and bounded confidence: models, analysis and simulation. *JASSS* 5(3):2. https://www.jasss.org/5/3/2.html
- Castellano, C., Fortunato, S., Loreto, V. (2009). Statistical physics of social dynamics. *Reviews of Modern Physics* 81(2):591–646. doi:10.1103/RevModPhys.81.591
- Flache, A., Mäs, M., Feliciani, T., Chattoe-Brown, E., Deffuant, G., Huet, S., Lorenz, J. (2017). Models of social influence: towards the next frontiers. *JASSS* 20(4):2. doi:10.18564/jasss.3521
- Dandekar, P., Goel, A., Lee, D.T. (2013). Biased assimilation, homophily, and the dynamics of polarization. *PNAS* 110(15):5791–5796. doi:10.1073/pnas.1217220110

**Polarization and echo chambers**
- Esteban, J.-M., Ray, D. (1994). On the measurement of polarization. *Econometrica* 62(4):819–851. doi:10.2307/2951734 [formula as restated in secondary literature]
- Garimella, K., De Francisci Morales, G., Gionis, A., Mathioudakis, M. (2018). Quantifying controversy on social media. *ACM Transactions on Social Computing* 1(1). doi:10.1145/3140565 (conference version WSDM 2016)
- Cinelli, M., De Francisci Morales, G., Galeazzi, A., Quattrociocchi, W., Starnini, M. (2021). The echo chamber effect on social media. *PNAS* 118(9):e2023301118. doi:10.1073/pnas.2023301118
- Musco, C., Musco, C., Tsourakakis, C.E. (2018). Minimizing polarization and disagreement in social networks. *WWW '18*, 369–378. doi:10.1145/3178876.3186103
- Morales, A.J., Borondo, J., Losada, J.C., Benito, R.M. (2015). Measuring political polarization: Twitter shows the two sides of Venezuela. *Chaos* 25(3):033114. doi:10.1063/1.4913758
- Guerra, P.C., Meira Jr., W., Cardie, C., Kleinberg, R. (2013). A measure of polarization on social media networks based on community boundaries. *ICWSM* 7(1):215–224. doi:10.1609/icwsm.v7i1.14421
- Krackhardt, D., Stern, R.N. (1988). Informal networks and organizational crises: An experimental simulation. *Social Psychology Quarterly* 51(2):123–140. doi:10.2307/2786835 [E-I index definition via secondary sources]
- Bail, C.A., et al. (2018). Exposure to opposing views on social media can increase political polarization. *PNAS* 115(37):9216–9221. doi:10.1073/pnas.1804840115
- Del Vicario, M., et al. (2016). The spreading of misinformation online. *PNAS* 113(3):554–559. doi:10.1073/pnas.1517441113
- Garimella, K., Weber, I. (2017). A long-term analysis of polarization on Twitter. *ICWSM* 11(1):528–531. doi:10.1609/icwsm.v11i1.14918
- Mohammad, S., Kiritchenko, S., Sobhani, P., Zhu, X., Cherry, C. (2016). SemEval-2016 Task 6: Detecting stance in tweets. *SemEval-2016*, 31–41. doi:10.18653/v1/S16-1003

**Recommenders and feed ranking**
- Chaney, A.J.B., Stewart, B.M., Engelhardt, B.E. (2018). How algorithmic confounding in recommendation systems increases homogeneity and decreases utility. *RecSys '18*, 224–232. doi:10.1145/3240323.3240370
- Jiang, R., Chiappa, S., Lattimore, T., György, A., Kohli, P. (2019). Degenerate feedback loops in recommender systems. *AIES '19*, 383–390. doi:10.1145/3306618.3314288
- Mansoury, M., Abdollahpouri, H., Pechenizkiy, M., Mobasher, B., Burke, R. (2020). Feedback loop and bias amplification in recommender systems. *CIKM '20*, 2145–2148. doi:10.1145/3340531.3412152
- Huszár, F., Ktena, S.I., O'Brien, C., Belli, L., Schlaikjer, A., Hardt, M. (2022). Algorithmic amplification of politics on Twitter. *PNAS* 119(1):e2025334119. doi:10.1073/pnas.2025334119
- Guess, A.M., et al. (2023). How do social media feed algorithms affect attitudes and behavior in an election campaign? *Science* 381(6656):398–404. doi:10.1126/science.abp9364 [two errata exist, 2024 and 2026; their content was not reviewed]
- Bakshy, E., Messing, S., Adamic, L.A. (2015). Exposure to ideologically diverse news and opinion on Facebook. *Science* 348(6239):1130–1132. doi:10.1126/science.aaa1160
- Radovanović, M., Nanopoulos, A., Ivanović, M. (2010). Hubs in space: Popular nearest neighbors in high-dimensional data. *JMLR* 11:2487–2531.
- Reddit hot ranking: reddit's archived open-source code, `r2/r2/lib/db/_sorts.pyx` (`_hot`), github.com/reddit-archive/reddit. Historical code; current production ranking is not public.

**LLM-agent social simulation: validity and biases**
- Yang, Z., et al. (2024). OASIS: Open Agent Social Interaction Simulations with One Million Agents. arXiv:2411.11581. Preprint; an earlier version appeared as a NeurIPS 2024 workshop poster. [its recommender formula was summarised by our literature check; confirm against the appendix before quoting]
- Park, J.S., O'Brien, J.C., Cai, C.J., Morris, M.R., Liang, P., Bernstein, M.S. (2023). Generative agents: Interactive simulacra of human behavior. *UIST '23*. doi:10.1145/3586183.3606763
- Park, J.S., Popowski, L., Cai, C.J., Morris, M.R., Liang, P., Bernstein, M.S. (2022). Social simulacra. *UIST '22*. doi:10.1145/3526113.3545616
- Törnberg, P., Valeeva, D., Uitermark, J., Bail, C. (2023). Simulating social media using large language models to evaluate alternative news feed algorithms. arXiv:2310.05984
- Larooij, M., Törnberg, P. (2025). Can we fix social media? Testing prosocial interventions using generative social simulation. arXiv:2508.03385
- Chuang, Y.-S., et al. (2024). Simulating opinion dynamics with networks of LLM-based agents. *Findings of NAACL 2024*, 3326–3346. doi:10.18653/v1/2024.findings-naacl.211
- Argyle, L.P., et al. (2023). Out of one, many: Using language models to simulate human samples. *Political Analysis* 31(3):337–351. doi:10.1017/pan.2023.2
- Santurkar, S., Durmus, E., Ladhak, F., Lee, C., Liang, P., Hashimoto, T. (2023). Whose opinions do language models reflect? *ICML 2023*, PMLR 202:29971–30004
- Bisbee, J., Clinton, J.D., Dorff, C., Kenkel, B., Larson, J.M. (2024). Synthetic replacements for human survey data? The perils of large language models. *Political Analysis* 32(4):401–416. doi:10.1017/pan.2024.5
- Wang, A., Morgenstern, J., Dickerson, J.P. (2025). Large language models that replace human participants can harmfully misportray and flatten identity groups. *Nature Machine Intelligence* 7(3):400–411. doi:10.1038/s42256-025-00986-z
- Park, P.S., Schoenegger, P., Zhu, C. (2024). Diminished diversity-of-thought in a standard large language model. *Behavior Research Methods* 56(6):5754–5770. doi:10.3758/s13428-023-02307-x
- Boelaert, J., Coavoux, S., Ollion, É., Petev, I., Präg, P. (2025). Machine bias. How do generative language models answer opinion polls? *Sociological Methods & Research* 54(3):1156–1196. doi:10.1177/00491241251330582
- Gao, C., et al. (2023). S³: Social-network simulation system with large language model-empowered agents. arXiv:2307.14984
- Mou, X., Wei, Z., Huang, X. (2024). Unveiling the truth and facilitating change: Towards agent-based large-scale social movement simulation. *Findings of ACL 2024*, 4789–4809. doi:10.18653/v1/2024.findings-acl.285
- Anthis, J.R., et al. (2025). Position: LLM social simulations are a promising research method. *ICML 2025*, PMLR 267:81005–81034
- Rossetti, G., et al. (2024). Y Social: an LLM-powered social media digital twin. arXiv:2408.00818
- Gao, C., et al. (2024). Large language models empowered agent-based modeling and simulation: a survey and perspectives. *Humanities and Social Sciences Communications* 11:1259. doi:10.1057/s41599-024-03611-3
- Weng, Z., Chen, G., Wang, W. (2025). Do as we do, not as you think: the conformity of large language models. *ICLR 2025*. arXiv:2501.13381
- Cho, Y.-M., Guntuku, S.C., Ungar, L. (2025). Herd behavior: Investigating peer influence in LLM-based multi-agent systems. arXiv:2505.21588 (preprint)
- Sharma, M., et al. (2024). Towards understanding sycophancy in language models. *ICLR 2024*. arXiv:2310.13548
- Liu, N.F., et al. (2024). Lost in the middle: How language models use long contexts. *TACL* 12:157–173. doi:10.1162/tacl_a_00638
- Padmakumar, V., He, H. (2024). Does writing with language models reduce content diversity? *ICLR 2024*. arXiv:2309.05196
- Wojcik, S., Hughes, A. (2019). Sizing up Twitter users. Pew Research Center, 24 April 2019.

**Forecast evaluation, calibration and ensembles**
- Brier, G.W. (1950). Verification of forecasts expressed in terms of probability. *Monthly Weather Review* 78(1):1–3. doi:10.1175/1520-0493(1950)078<0001:VOFEIT>2.0.CO;2
- Murphy, A.H. (1973). A new vector partition of the probability score. *Journal of Applied Meteorology* 12(4):595–600. doi:10.1175/1520-0450(1973)012<0595:ANVPOT>2.0.CO;2
- Matheson, J.E., Winkler, R.L. (1976). Scoring rules for continuous probability distributions. *Management Science* 22(10):1087–1096. doi:10.1287/mnsc.22.10.1087
- Gneiting, T., Raftery, A.E. (2007). Strictly proper scoring rules, prediction, and estimation. *JASA* 102(477):359–378. doi:10.1198/016214506000001437
- Gneiting, T., Balabdaoui, F., Raftery, A.E. (2007). Probabilistic forecasts, calibration and sharpness. *JRSS-B* 69(2):243–268. doi:10.1111/j.1467-9868.2007.00587.x
- Diebold, F.X., Mariano, R.S. (1995). Comparing predictive accuracy. *Journal of Business & Economic Statistics* 13(3):253–263. doi:10.1080/07350015.1995.10524599
- Leutbecher, M., Palmer, T.N. (2008). Ensemble forecasting. *Journal of Computational Physics* 227(7):3515–3539. doi:10.1016/j.jcp.2007.02.014
- Baron, J., Mellers, B.A., Tetlock, P.E., Stone, E., Ungar, L.H. (2014). Two reasons to make aggregated probability forecasts more extreme. *Decision Analysis* 11(2):133–145. doi:10.1287/deca.2014.0293
- Mellers, B., et al. (2014). Psychological strategies for winning a geopolitical forecasting tournament. *Psychological Science* 25(5):1106–1115. doi:10.1177/0956797614524255
- Tetlock, P.E., Gardner, D. (2015). *Superforecasting: The Art and Science of Prediction*. Crown.
- Halawi, D., Zhang, F., Chen, Y.-H., Steinhardt, J. (2024). Approaching human-level forecasting with language models. *NeurIPS 2024*. arXiv:2402.18563
- Karger, E., et al. (2025). ForecastBench: A dynamic benchmark of AI forecasting capabilities. *ICLR 2025*. arXiv:2409.19839 [reported figures differ between arXiv versions]
- Paleka, D., Goel, S., Geiping, J., Tramèr, F. (2025). Pitfalls in evaluating language model forecasters. arXiv:2506.00723
- Glasserman, P., Lin, C. (2023). Assessing look-ahead bias in stock return predictions generated by GPT sentiment analysis. arXiv:2309.17322
- Platt, D. (2020). A comparison of economic agent-based model calibration methods. *Journal of Economic Dynamics and Control* 113:103859. doi:10.1016/j.jedc.2020.103859
- Grazzini, J., Richiardi, M.G., Tsionas, M. (2017). Bayesian estimation of agent-based models. *Journal of Economic Dynamics and Control* 77:26–47. doi:10.1016/j.jedc.2017.01.014
- Lamperti, F., Roventini, A., Sani, A. (2018). Agent-based model calibration using machine learning surrogates. *Journal of Economic Dynamics and Control* 90:366–389. doi:10.1016/j.jedc.2018.03.011

**Communicating uncertainty**
- Gigerenzer, G., Hoffrage, U. (1995). How to improve Bayesian reasoning without instruction: Frequency formats. *Psychological Review* 102(4):684–704. doi:10.1037/0033-295X.102.4.684
- Spiegelhalter, D., Pearson, M., Short, I. (2011). Visualizing uncertainty about the future. *Science* 333(6048):1393–1400. doi:10.1126/science.1191181
- Hullman, J., Resnick, P., Adar, E. (2015). Hypothetical outcome plots outperform error bars and violin plots for inferences about reliability of variable ordering. *PLOS ONE* 10(11):e0142444. doi:10.1371/journal.pone.0142444
- Kay, M., Kola, T., Hullman, J.R., Munson, S.A. (2016). When (ish) is my bus? User-centered visualizations of uncertainty in everyday, mobile predictive systems. *CHI '16*, 5092–5103. doi:10.1145/2858036.2858558
- van der Bles, A.M., et al. (2019). Communicating uncertainty about facts, numbers and science. *Royal Society Open Science* 6(5):181870. doi:10.1098/rsos.181870

---

## Appendix A. Code reference index

| Topic | Location |
|---|---|
| Activation | `backend/scripts/run_parallel_simulation.py:1040-1092`; called at `:1239`, `:1438` |
| Action sets | `run_parallel_simulation.py:177-202` |
| Seed posts | `run_parallel_simulation.py:1173-1210` (Twitter dict), `:1364-1409` (Reddit lists) |
| Round loop and LLM step | `run_parallel_simulation.py:1228-1275`, `:1427-1474` |
| JSONL logging | `run_parallel_simulation.py:611, 657-746, 749` ff.; `scripts/action_logger.py:98, 271` |
| Model creation | `run_parallel_simulation.py:984-1037` |
| Config dataclasses | `backend/app/services/simulation_config_generator.py:52-144`; platform weights `:341-359`; `scheduled_events=[]` `:725` |
| Analytics | `backend/app/services/simulation_analytics.py:22-50, 86, 225` |
| Zep write-back | `backend/app/services/zep_graph_memory_updater.py:36-67, 228, 371-373`; `simulation_runner.py:872` |
| Report | `backend/app/services/report_agent.py:552-700, 871-960, 1221, 1346`; `zep_tools.py:943, 1143, 1270, 1549` |
| OASIS env | `oasis/environment/env.py:78-97, 103, 152, 193, 198` |
| Refresh and rec update | `oasis/social_platform/platform.py:258-326, 328-398`; repost/quote/like `:430-616` |
| Recommenders | `oasis/social_platform/recsys.py:168-259` (Reddit), `:419-606` (TwHIN) |
| Feed serialisation (D1) | `oasis/social_platform/platform_utils.py:75-186` |
| Observation | `oasis/social_agent/agent_environment.py:49-53, 118-135` |
| Agent and prompt | `oasis/social_agent/agent.py:106-151`; `oasis/social_platform/config/user.py:50-111` |
| Clock | `oasis/clock/clock.py:28`; `platform.py:77` |
| Memory | `camel/agents/chat_agent.py:477-487`; `camel/types/unified_model_type.py:64-71` |

## Appendix B. Reproducing Section 2

All queries are read-only against `backend/uploads/simulations/sim_168d7ecb477b/`.

```sql
-- twitter_simulation.db: action mix by step (step 0 = seed posts)
SELECT created_at, action, COUNT(*) FROM trace WHERE action <> 'sign_up' GROUP BY 1, 2;

-- cascade parents: use the trace, not post.original_post_id (OASIS rewrites it to the root)
SELECT json_extract(info, '$.new_post_id') AS child,
       COALESCE(json_extract(info, '$.quoted_id'), json_extract(info, '$.reposted_id')) AS parent
FROM trace WHERE action IN ('quote_post', 'repost');

-- exposures: one row per post shown in a refresh
SELECT t.user_id, t.created_at, json_extract(p.value, '$.post_id') AS post_id, p.key AS position
FROM trace t, json_each(json_extract(t.info, '$.posts')) p WHERE t.action = 'refresh';

-- blind activations: (user, step) with an action but no refresh row
SELECT user_id, created_at FROM trace WHERE action NOT IN ('sign_up', 'refresh') AND created_at <> '0'
EXCEPT SELECT user_id, created_at FROM trace WHERE action = 'refresh';

-- quotes store the ORIGINAL text in `content`
SELECT COUNT(*), SUM(p.content = o.content) FROM post p JOIN post o ON p.original_post_id = o.post_id
WHERE p.quote_content IS NOT NULL;
```

D1 reproduction: call `PlatformUtils._add_comments_to_posts` on the rows of a feed whose lowest `post_id` is a quote
(for example posts 23 and 68). It raises `UnboundLocalError: cannot access local variable 'num_reports'`. Of the 74
feeds in the final rec table, 48 trigger it. This was tested on a copy of the database, not the original.
