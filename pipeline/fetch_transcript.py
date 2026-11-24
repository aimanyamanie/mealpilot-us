"""YouTube transcript -> pipeline/data/transcripts/<video_id>.json, byte for byte as
TranscriptAPI returns it (the same format as every file already there).

    python fetch_transcript.py 6-m_u_8r81o https://youtu.be/XXXXXXXXXXX ...
    python fetch_transcript.py --force 6-m_u_8r81o     # re-fetch an existing file

Needs TRANSCRIPT_API_KEY in .env. Costs 1 TranscriptAPI credit per video, charged
only on success. Existing files are skipped (no credit) unless --force.
Asks for English captions, preferring the creator's own track over auto-generated.
"""
import json
import re
import sys

import requests

from db import env
from measures import HERE

API = "https://transcriptapi.com/api/v2/youtube/transcript"
OUT = HERE / "data" / "transcripts"


def video_id(arg):
    m = re.search(r"(?:v=|youtu\.be/|shorts/|embed/)([\w-]{11})", arg)
    if m:
        return m.group(1)
    if re.fullmatch(r"[\w-]{11}", arg):
        return arg
    raise SystemExit(f"not a YouTube URL or video id: {arg!r}")


def fetch(vid, force=False):
    path = OUT / f"{vid}.json"
    if path.exists() and not force:
        print(f"{vid}: already saved, skipped (use --force to re-fetch)")
        return 0
    r = requests.get(API, timeout=120,
                     headers={"Authorization": f"Bearer {env('TRANSCRIPT_API_KEY')}"},
                     params={"video_url": vid, "format": "json", "include_timestamp": "true",
                             "send_metadata": "true", "language": "en"})
    if r.status_code != 200:
        print(f"{vid}: HTTP {r.status_code} {r.text[:300]}")
        return 1
    data = r.json()
    if data.get("video_id") != vid or not data.get("transcript"):
        print(f"{vid}: unexpected response, not saved: {r.text[:300]}")
        return 1
    OUT.mkdir(parents=True, exist_ok=True)
    path.write_bytes(r.content)
    md = data.get("metadata") or {}
    print(f"{vid}: saved {len(data['transcript'])} segments, language {data.get('language')}, "
          f"{data.get('lengthText')}  {md.get('author_name')} - {md.get('title')}")
    return 0


if __name__ == "__main__":
    args = sys.argv[1:]
    force = "--force" in args
    ids = [video_id(a) for a in args if a != "--force"]
    if not ids:
        raise SystemExit(__doc__)
    sys.exit(max(fetch(v, force) for v in ids))
