"""The fixes Hivemind applies to OASIS at simulation start."""

import asyncio
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

pytest.importorskip("oasis")
import oasis_patches  # noqa: E402


class FakeUtils:
    """Just enough of PlatformUtils to run _add_comments_to_posts on a real table."""

    show_score = False
    report_threshold = 2

    def __init__(self):
        db = sqlite3.connect(":memory:")
        db.executescript("""
            CREATE TABLE post (post_id INTEGER PRIMARY KEY, user_id INT, original_post_id INT, content TEXT,
                quote_content TEXT, created_at TEXT, num_likes INT, num_dislikes INT, num_shares INT, num_reports INT);
            CREATE TABLE comment (comment_id INTEGER PRIMARY KEY, post_id INT, user_id INT, content TEXT,
                created_at TEXT, num_likes INT, num_dislikes INT);
            INSERT INTO post VALUES (1, 10, NULL, 'Original post', NULL, '1', 0, 0, 0, 0);
            INSERT INTO post VALUES (2, 11, 1, 'Original post', 'My take on it', '2', 0, 0, 0, 0);
        """)
        self.db_cursor = db.cursor()

    def _get_post_type(self, post_id):
        return {"type": "quote" if post_id == 2 else "common", "root_post_id": 1}

    def rows(self, *ids):
        marks = ",".join("?" * len(ids))
        self.db_cursor.execute(
            "SELECT post_id, user_id, original_post_id, content, quote_content, created_at, num_likes, "
            f"num_dislikes, num_shares FROM post WHERE post_id IN ({marks}) ORDER BY post_id DESC", ids)
        return self.db_cursor.fetchall()


def test_a_feed_that_starts_with_a_quote_no_longer_crashes():
    from oasis.social_platform.platform_utils import PlatformUtils

    notes = oasis_patches.apply()
    assert any(n.startswith("quote-feed fix: ") and "SKIPPED" not in n and "FAILED" not in n for n in notes), notes

    utils = FakeUtils()
    posts = PlatformUtils._add_comments_to_posts(utils, utils.rows(2, 1))    # the quote comes first
    assert [p["post_id"] for p in posts] == [2, 1]
    assert "My take on it" in posts[0]["content"] and "Original post" in posts[0]["content"]

    assert "already applied" in oasis_patches.apply()[0]                      # safe to call twice


def test_failed_feeds_are_printed(capsys):
    from oasis.social_platform.platform import Platform

    oasis_patches.apply()

    class Broken:
        recsys_type = None
        sandbox_clock = type("Clock", (), {"get_time_step": lambda self: 1})()
        # no pl_utils: the body fails inside OASIS's own try block

    async def run():
        # The unpatched body fails at once on this stand-in and returns an error dict.
        return await Platform.refresh(Broken(), 7)

    result = asyncio.run(run())
    assert result.get("error")
    assert "[feed-error] agent 7" in capsys.readouterr().out
