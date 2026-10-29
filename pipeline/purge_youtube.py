"""TEST ONLY: enforce the 30-day limit on YouTube API data.

    python purge_youtube.py            # run at least weekly while testing

Deletes raw files in data/youtube/ fetched more than 30 days ago, and on the
dev-youtube-test branch deletes recipes whose video data is older than that
(their lines and nutrition go with them). Re-fetching resets the clock.
"""
import json
from datetime import datetime, timedelta, timezone

from youtube_test import DATA, RETENTION_DAYS, connect


def main() -> None:
    cutoff = datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)
    removed_files = 0
    for path in DATA.glob("*.json"):
        fetched = datetime.fromisoformat(json.loads(path.read_text(encoding="utf-8"))["fetched_at"])
        if fetched < cutoff:
            path.unlink()
            removed_files += 1
    with connect() as conn:
        n = conn.execute("DELETE FROM recipes WHERE video_checked_at < %s OR video_checked_at IS NULL",
                         [cutoff]).rowcount
    print(f"removed {removed_files} raw files and {n} recipes older than {RETENTION_DAYS} days")


if __name__ == "__main__":
    main()
