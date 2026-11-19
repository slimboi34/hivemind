"""
Fixes applied to the OASIS library when a simulation starts.

OASIS is a pinned dependency, so its files are not edited in place. Each fix
here checks that the faulty code is still what it expects before changing it
and does nothing otherwise, so an upstream fix or a version bump cannot be
broken by a stale patch. apply() reports what it did, and the run scripts
print that at start so every simulation log records which fixes were active.

Fixes:
1. Quote posts crash the feed. PlatformUtils._add_comments_to_posts never sets
   num_reports for a quote post. When a quote is the first post in a feed the
   function raises UnboundLocalError; Platform.refresh swallows it and the
   agent is told there are no posts. In stored runs this blinded 17-46% of
   turns on the short-post platform. The fix reads num_reports for the quote.
2. Feed failures are silent. Platform.refresh returns the error to the agent
   and logs nothing. It now also prints one "[feed-error]" line, which lands
   in the run's simulation.log.
3. The Twitter recommender embeds everything in one batch. Every round it runs
   all user profiles and posts (up to 1,000 texts of up to 512 tokens) through
   twhin-bert in a single forward pass. Attention memory grows with the post
   count: by round 6 of a 52-agent run one process held 6.8 GB and swapped to
   a standstill, and on a container it would be killed. Embeddings are the
   [CLS] pooler output under an attention mask, so they do not depend on what
   else is in the batch; encoding in batches of HIVEMIND_EMBED_BATCH (default
   32) gives the same vectors with a fraction of the memory. Recommendations,
   and so forecasts, are unchanged.
"""

from __future__ import annotations

import inspect
import textwrap
from typing import List

QUOTE_BRANCH = 'elif post_type_result["type"] == "quote":'
QUOTE_FIX = '''
                self.db_cursor.execute(
                    "SELECT num_reports FROM post WHERE post_id = ?",
                    (post_id, ))
                num_reports = self.db_cursor.fetchone()[0]'''


def _patch_quote_feed() -> str:
    from oasis.social_platform import platform_utils

    cls = platform_utils.PlatformUtils
    if getattr(cls._add_comments_to_posts, "_hivemind_patched", False):
        return "quote-feed fix: already applied"
    source = textwrap.dedent(inspect.getsource(cls._add_comments_to_posts))
    start = source.find(QUOTE_BRANCH)
    end = source.find('elif post_type_result["type"] == "common":')
    if source.count(QUOTE_BRANCH) != 1 or end < start:
        return "quote-feed fix: SKIPPED, the library code is not what the patch expects"
    if "num_reports" in source[start:end]:
        return "quote-feed fix: not needed, the library already handles quotes"
    line_start = source.rfind("\n", 0, start) + 1
    body_indent = " " * (start - line_start + 4)
    fix = "".join("\n" + body_indent + line for line in textwrap.dedent(QUOTE_FIX).strip("\n").split("\n"))
    fixed = source.replace(QUOTE_BRANCH, QUOTE_BRANCH + fix, 1)
    namespace: dict = {}
    exec(compile(fixed, platform_utils.__file__ + " (hivemind quote-feed fix)", "exec"),
         platform_utils.__dict__, namespace)
    patched = namespace["_add_comments_to_posts"]
    patched._hivemind_patched = True
    cls._add_comments_to_posts = patched
    return "quote-feed fix: applied"


def _patch_refresh_logging() -> str:
    from oasis.social_platform import platform as platform_module

    cls = platform_module.Platform
    original = cls.refresh
    if getattr(original, "_hivemind_patched", False):
        return "feed-error logging: already applied"

    async def refresh(self, agent_id: int):
        result = await original(self, agent_id)
        if isinstance(result, dict) and result.get("error"):
            print(f"[feed-error] agent {agent_id} got no feed: {result['error']}", flush=True)
        return result

    refresh._hivemind_patched = True
    cls.refresh = refresh
    return "feed-error logging: applied"


def _patch_embedding_batch() -> str:
    import os
    from oasis.social_platform import recsys

    original = getattr(recsys, 'generate_post_vector', None)
    if original is None:
        return 'embedding batch: skipped (recsys.generate_post_vector not found)'
    if getattr(original, '_hivemind_batched', False):
        return 'embedding batch: already applied'
    params = list(inspect.signature(original).parameters)
    if params[:4] != ['model', 'tokenizer', 'texts', 'batch_size']:
        return f'embedding batch: skipped (unexpected signature {params})'
    try:
        cap = max(1, int(os.environ.get('HIVEMIND_EMBED_BATCH', '32')))
    except ValueError:
        cap = 32

    def generate_post_vector(model, tokenizer, texts, batch_size):
        return original(model, tokenizer, texts, min(batch_size, cap))

    generate_post_vector._hivemind_batched = True
    recsys.generate_post_vector = generate_post_vector
    return f'embedding batch: twhin-bert encodes {cap} texts at a time'


def apply() -> List[str]:
    """Apply every fix. Never raises: a patch that cannot apply says so instead."""
    notes = []
    for patch in (_patch_quote_feed, _patch_refresh_logging, _patch_embedding_batch):
        try:
            notes.append(patch())
        except Exception as error:  # a broken patch must not stop a run
            notes.append(f"{patch.__name__}: FAILED ({error})")
    return notes
