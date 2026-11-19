"""
Accounts that join a run while it is under way.

The cast a run starts with is fixed at setup. In a real event the conversation
widens: when a thread takes off, the people around the actors in it are pulled
in, and so are people affected by a narrow angle nobody present speaks for.
The SpawnDirector looks at what drew attention every few rounds, asks the model
who would join now, and registers those accounts on the live platforms.

One director serves every platform in the process, so an account that joins
has the same id and persona on each. Whichever platform reaches a round first
decides that round's newcomers; the others get the same answer.

The rules, prompts and limits live in app/services/cast_growth.py, which this
file loads by path so the subprocess does not import the Flask app.
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import os
from typing import Any, Callable, Dict, List, Optional


def _load_growth():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app", "services", "cast_growth.py")
    spec = importlib.util.spec_from_file_location("hivemind_cast_growth", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


growth = _load_growth()

LANGUAGE_NOTE = "Write every text field in the same language as the question."


class SpawnDirector:
    def __init__(self, config: Dict[str, Any], simulation_dir: str,
                 log: Callable[[str], None] = print, ask: Optional[Callable] = None):
        self.config = config
        self.dir = simulation_dir
        self.log = log
        self.opts = growth.settings(config)
        evidence = sum(1 for c in config.get("agent_configs") or []
                       if c.get("origin", growth.ORIGIN_EVIDENCE) == growth.ORIGIN_EVIDENCE)
        self.opts["join_max"] = growth.cap_for(evidence, self.opts["join_max"])
        self._ask = ask or self._ask_model
        self._lock = asyncio.Lock()
        self._waves: Dict[int, List[Dict[str, Any]]] = {}
        self._seen: List[Dict[str, Any]] = []
        self._joined = 0

        # A rerun of the same simulation starts from the cast that was set up.
        _, removed = growth.split_original(config)
        if removed:
            self._drop_from_files(set(removed))
            self.log(f"[cast-growth] removed {len(removed)} accounts that joined during an earlier run")
        self._write_report()
        if self.opts["join"] and self.opts["join_max"]:
            self.log(
                f"[cast-growth] on: up to {self.opts['join_per_wave']} newcomers every "
                f"{self.opts['join_every']} rounds from round {self.opts['join_first_round']}, "
                f"{self.opts['join_max']} at most"
            )
        else:
            self.log("[cast-growth] off: the cast is fixed for this run")

    # ------------------------------------------------------------ the setup circle

    def circle_follows(self) -> List[tuple]:
        """(follower id, followee id) for every circle account: it follows its anchor."""
        return [
            (c["agent_id"], c["anchor_agent_id"])
            for c in self.config.get("agent_configs") or []
            if c.get("origin") == growth.ORIGIN_CIRCLE and c.get("anchor_agent_id") is not None
        ]

    async def apply_circle_follows(self, env, platform: str) -> int:
        """Run before the opening posts. Returns how many follow edges were made."""
        done = 0
        for follower, followee in self.circle_follows():
            try:
                agent = env.agent_graph.get_agent(follower)
                result = await agent.env.action.follow(followee)
                done += bool(result and result.get("success"))
            except Exception as e:
                self.log(f"[cast-growth] {platform}: follow {follower}->{followee} failed: {e}")
        if done:
            self.log(f"[cast-growth] {platform}: {done} circle accounts follow their anchor")
        return done

    # ------------------------------------------------------------------ joiners

    def observe(self, actions: List[Dict[str, Any]]) -> None:
        """Everything a platform logged this round, for the next look."""
        self._seen.extend(actions)

    async def wave_for(self, round_num: int) -> List[Dict[str, Any]]:
        """The accounts that join at the start of this round (rounds count from 1). May be empty."""
        opts = self.opts
        if not (opts["join"] and opts["join_max"] and opts["join_per_wave"]):
            return []
        if not growth.wave_due(round_num, opts["join_first_round"], opts["join_every"]):
            return []
        async with self._lock:
            if round_num in self._waves:
                return self._waves[round_num]
            self._waves[round_num] = await self._decide(round_num)
            return self._waves[round_num]

    async def _decide(self, round_num: int) -> List[Dict[str, Any]]:
        room = min(self.opts["join_per_wave"], self.opts["join_max"] - self._joined)
        seen, self._seen = self._seen, []
        hot = growth.hot_threads(seen)
        if room <= 0 or not hot:
            return []
        cast = [
            {"agent_id": c["agent_id"], "name": c.get("entity_name") or "", "entity_type": c.get("entity_type")}
            for c in self.config.get("agent_configs") or []
        ]
        try:
            system, user = growth.wave_prompt(
                self.config.get("simulation_requirement") or "", cast, hot, room, round_num,
                LANGUAGE_NOTE,
            )
            rows = growth.parse_accounts(growth.parse_json(await self._ask(system, user)), cast, limit=room)
        except Exception as e:
            self.log(f"[cast-growth] round {round_num}: no newcomers, the model call failed: {e}")
            return []

        next_id = max((c["agent_id"] for c in cast), default=-1) + 1
        wave = []
        for offset, row in enumerate(rows):
            agent_id = next_id + offset
            cfg = growth.agent_config_row(row, agent_id, growth.ORIGIN_JOINED, joined_round=round_num)
            wave.append({"agent_id": agent_id, "row": row, "config": cfg, "profile": growth.profile_row(row, agent_id)})
        if not wave:
            self.log(f"[cast-growth] round {round_num}: nobody new would join")
            return []

        # The shared config is what every platform loop reads to pick who acts.
        self.config.setdefault("agent_configs", []).extend(w["config"] for w in wave)
        self._joined += len(wave)
        self._persist(wave)
        for w in wave:
            near = f" (around {w['row']['anchor_name']})" if w["row"].get("anchor_name") else ""
            self.log(f"[cast-growth] round {round_num}: {w['row']['name']}{near} joins. {w['row']['why']}")
        return wave

    async def join(self, env, platform: str, wave: List[Dict[str, Any]], model, available_actions,
                   agent_names: Dict[int, str]) -> List[tuple]:
        """Register this round's newcomers on one platform. Returns [(agent_id, agent)]."""
        if not wave:
            return []
        from oasis import SocialAgent, UserInfo

        joined = []
        for w in wave:
            agent_id, profile = w["agent_id"], w["profile"]
            try:
                if platform == "reddit":
                    info = UserInfo(
                        name=profile["username"], description=profile["bio"], recsys_type="reddit",
                        profile={"nodes": [], "edges": [], "other_info": {
                            "user_profile": profile["persona"], "mbti": profile["mbti"],
                            "gender": profile["gender"], "age": profile["age"], "country": profile["country"],
                        }},
                    )
                else:
                    info = UserInfo(
                        name=profile["username"], description=profile["bio"], recsys_type="twitter",
                        profile={"nodes": [], "edges": [], "other_info": {
                            "user_profile": f"{profile['bio']} {profile['persona']}",
                        }},
                    )
                agent = SocialAgent(agent_id=agent_id, user_info=info, model=model,
                                    agent_graph=env.agent_graph, available_actions=available_actions)
                agent.channel = env.channel
                agent.env.action.channel = env.channel
                env.agent_graph.add_agent(agent)
                signed = await agent.env.action.sign_up(
                    user_name=info.user_name, name=info.name, bio=info.description)
                if not (signed and signed.get("success")):
                    raise RuntimeError(f"sign-up refused: {signed}")
                anchor = w["row"].get("anchor_agent_id")
                if anchor is not None:
                    await agent.env.action.follow(anchor)
                agent_names[agent_id] = w["row"]["name"]
                joined.append((agent_id, agent))
            except Exception as e:
                self.log(f"[cast-growth] {platform}: {w['row']['name']} could not join: {e}")
        return joined

    # ---------------------------------------------------------------- files

    async def _ask_model(self, system: str, user: str) -> str:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(
            api_key=os.environ.get("LLM_API_KEY") or os.environ.get("OPENAI_API_KEY"),
            base_url=os.environ.get("LLM_BASE_URL") or os.environ.get("OPENAI_API_BASE_URL") or None,
        )
        reply = await client.chat.completions.create(
            model=os.environ.get("LLM_MODEL_NAME") or self.config.get("llm_model") or "gpt-4o-mini",
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            # No temperature: some models reject the parameter outright.
            max_tokens=3000,
        )
        return reply.choices[0].message.content or ""

    def _read(self, name: str) -> Any:
        try:
            with open(os.path.join(self.dir, name), encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return None

    def _persist(self, wave: List[Dict[str, Any]]) -> None:
        """Add the newcomers to the files the rest of Hivemind reads the cast from."""
        try:
            on_disk = self._read("simulation_config.json")
            if isinstance(on_disk, dict):
                on_disk.setdefault("agent_configs", []).extend(w["config"] for w in wave)
                growth.write_json(os.path.join(self.dir, "simulation_config.json"), on_disk)
            profiles = self._read("reddit_profiles.json")
            if isinstance(profiles, list):
                profiles.extend(w["profile"] for w in wave)
                growth.write_json(os.path.join(self.dir, "reddit_profiles.json"), profiles)
            self._write_report()
        except OSError as e:
            self.log(f"[cast-growth] could not save the newcomers: {e}")

    def _drop_from_files(self, ids: set) -> None:
        try:
            on_disk = self._read("simulation_config.json")
            if isinstance(on_disk, dict):
                growth.split_original(on_disk)
                growth.write_json(os.path.join(self.dir, "simulation_config.json"), on_disk)
            profiles = self._read("reddit_profiles.json")
            if isinstance(profiles, list):
                kept = [p for p in profiles if p.get("user_id") not in ids]
                growth.write_json(os.path.join(self.dir, "reddit_profiles.json"), kept)
        except OSError as e:
            self.log(f"[cast-growth] could not reset the cast files: {e}")

    def _write_report(self) -> None:
        """cast_growth.json: the settings in force and who joined, for the health check and the UI."""
        joined = [c for c in self.config.get("agent_configs") or [] if c.get("origin") == growth.ORIGIN_JOINED]
        try:
            growth.write_json(os.path.join(self.dir, growth.GROWTH_FILE), {
                "settings": self.opts,
                "joined": [
                    {k: c.get(k) for k in ("agent_id", "entity_name", "entity_type", "anchor_name",
                                           "relation", "why", "joined_round")}
                    for c in joined
                ],
            })
        except OSError:
            pass
