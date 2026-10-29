"""TEST ONLY: fetch recent uploads of the channels in test_channels.csv.

    python fetch_youtube.py                 # latest 50 uploads per channel
    python fetch_youtube.py --limit 200
    python fetch_youtube.py --only sip-and-feast

Writes data/youtube/<slug>.json (gitignored), each video stamped with
fetched_at so purge_youtube.py can enforce the 30-day limit. See CLAUDE.md,
Recipe sourcing, test-only exception: nothing here may reach main.

Quota: channels.list 1 unit per channel, playlistItems.list 1 per 50 ids,
videos.list 1 per 50 ids. search.list (100 units) is never used.
Captions are never fetched.
"""
import argparse
import csv
import json
import re
import sys
from datetime import datetime, timezone

import requests

from youtube_test import DATA, HERE, api_key

API = "https://www.googleapis.com/youtube/v3"
ISO_DUR = re.compile(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?")


def get(endpoint: str, **params) -> dict:
    params["key"] = api_key()
    r = requests.get(f"{API}/{endpoint}", params=params, timeout=30)
    if r.status_code == 403:
        sys.exit(f"403: quota exhausted or YouTube Data API v3 not enabled.\n{r.text[:300]}")
    r.raise_for_status()
    return r.json()


def channel(handle: str):
    items = get("channels", part="snippet,statistics,contentDetails",
                forHandle=handle).get("items", [])
    if not items:
        return None
    c = items[0]
    return {
        "channel_id": c["id"],
        "title": c["snippet"]["title"],
        "subscriber_count": int(c["statistics"].get("subscriberCount", 0) or 0),
        "video_count": int(c["statistics"].get("videoCount", 0) or 0),
        "avatar_url": c["snippet"]["thumbnails"]["high"]["url"],
        "uploads_playlist": c["contentDetails"]["relatedPlaylists"]["uploads"],
    }


def upload_ids(playlist_id: str, limit: int) -> list[str]:
    ids, token = [], None
    while len(ids) < limit:
        data = get("playlistItems", part="contentDetails", playlistId=playlist_id,
                   maxResults=50, pageToken=token)
        ids += [i["contentDetails"]["videoId"] for i in data.get("items", [])]
        token = data.get("nextPageToken")
        if not token:
            break
    return ids[:limit]


def duration(iso: str) -> int:
    m = ISO_DUR.fullmatch(iso or "")
    if not m:
        return 0
    h, mi, s = (int(x) if x else 0 for x in m.groups())
    return h * 3600 + mi * 60 + s


def videos(ids: list[str], fetched_at: str) -> list[dict]:
    out = []
    for i in range(0, len(ids), 50):
        data = get("videos", part="snippet,contentDetails", id=",".join(ids[i:i + 50]))
        for v in data.get("items", []):
            sn = v["snippet"]
            thumbs = sn.get("thumbnails", {})
            out.append({
                "video_id": v["id"],
                "title": sn["title"],
                "description": sn.get("description", ""),
                "published_at": sn["publishedAt"],
                "thumbnail_url": (thumbs.get("maxres") or thumbs.get("high") or {}).get("url"),
                "duration_seconds": duration(v["contentDetails"].get("duration")),
                "fetched_at": fetched_at,
            })
    return out


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=50)
    ap.add_argument("--only")
    args = ap.parse_args(argv)
    DATA.mkdir(parents=True, exist_ok=True)
    fetched_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with (HERE / "test_channels.csv").open(encoding="utf-8", newline="") as f:
        channels = [r for r in csv.DictReader(f) if not args.only or r["slug"] == args.only]
    for row in channels:
        info = channel(row["handle"])
        if not info:
            print(f"{row['slug']}: handle {row['handle']} not found")
            continue
        vids = videos(upload_ids(info["uploads_playlist"], args.limit), fetched_at)
        out = DATA / f"{row['slug']}.json"
        out.write_text(json.dumps({"creator": {**row, **info}, "fetched_at": fetched_at,
                                   "videos": vids}, indent=1), encoding="utf-8")
        print(f"{row['slug']}: {len(vids)} videos -> {out.name}")


if __name__ == "__main__":
    main()
