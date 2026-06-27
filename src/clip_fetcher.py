"""
clip_fetcher.py
Fetches viral video clips from:
  - Reddit JSON API (no auth needed, completely free)
  - YouTube via yt-dlp with rate-limit handling
"""

import os
import re
import json
import time
import random
import subprocess
import requests
from pathlib import Path


RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY", "")
OUTPUT_DIR = Path("output/clips")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

VIRAL_SUBREDDITS = [
    "nextfuckinglevel", "PublicFreakout", "maybemaybemaybe",
    "therewasanattempt", "instant_regret", "unexpected",
    "interestingasfuck", "oddlysatisfying", "Whatcouldgowrong",
    "holdmyfeedingtube", "AbruptChaos", "nonononoyes",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; viral-pipeline/1.0)"
}


# ─────────────────────────────────────────────
# REDDIT via public JSON API (no auth needed)
# ─────────────────────────────────────────────

def fetch_reddit_clips(trending_topics: list[str], max_clips: int = 5) -> list[dict]:
    clips = []
    subs = random.sample(VIRAL_SUBREDDITS, min(6, len(VIRAL_SUBREDDITS)))

    for sub in subs:
        if len(clips) >= max_clips:
            break
        posts = _reddit_hot(sub)
        for post in posts:
            if len(clips) >= max_clips:
                break
            url = post.get("url", "")
            if not _is_video_url(url):
                continue
            clip_path = _download_clip(url, source="reddit", title=post.get("title", ""))
            if clip_path:
                clips.append({
                    "path": str(clip_path),
                    "title": post.get("title", ""),
                    "source": "reddit",
                    "topic": trending_topics[0] if trending_topics else "viral",
                    "score": post.get("score", 0),
                    "url": url,
                    "description": post.get("selftext", "")[:300],
                })
        time.sleep(random.uniform(1.0, 2.5))

    # Also try SocialGrep if key is available (best-effort, not required)
    if RAPIDAPI_KEY and len(clips) < max_clips:
        sg_clips = _socialgrep_fetch(trending_topics, max_clips - len(clips))
        clips.extend(sg_clips)

    print(f"[Reddit] Downloaded {len(clips)} clips")
    return clips


def _reddit_hot(subreddit: str, limit: int = 10) -> list[dict]:
    """Fetch hot posts from a subreddit using Reddit's public JSON API."""
    url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit={limit}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        posts = data["data"]["children"]
        result = []
        for p in posts:
            d = p["data"]
            # Only video posts
            if d.get("is_video") or "v.redd.it" in d.get("url", "") or \
               d.get("post_hint") == "hosted:video":
                result.append(d)
        return result
    except Exception as e:
        print(f"[Reddit] r/{subreddit} failed: {e}")
        return []


def _socialgrep_fetch(trending_topics: list[str], max_clips: int) -> list[dict]:
    """Try SocialGrep as optional bonus source."""
    clips = []
    for topic in trending_topics[:2]:
        try:
            url = "https://socialgrep.p.rapidapi.com/search/posts"
            headers = {
                "x-rapidapi-host": "socialgrep.p.rapidapi.com",
                "x-rapidapi-key": RAPIDAPI_KEY,
            }
            resp = requests.get(url, headers=headers,
                                params={"query": topic}, timeout=15)
            resp.raise_for_status()
            posts = resp.json().get("data", [])
            for post in posts:
                if len(clips) >= max_clips:
                    break
                video_url = post.get("url", "")
                if not _is_video_url(video_url):
                    continue
                path = _download_clip(video_url, source="reddit_sg",
                                      title=post.get("title", ""))
                if path:
                    clips.append({
                        "path": str(path),
                        "title": post.get("title", ""),
                        "source": "reddit",
                        "topic": topic,
                        "score": post.get("score", 0),
                        "url": video_url,
                        "description": "",
                    })
        except Exception as e:
            print(f"[SocialGrep] {e} — skipping")
        time.sleep(1.5)
    return clips


# ─────────────────────────────────────────────
# YOUTUBE via yt-dlp
# ─────────────────────────────────────────────

def fetch_youtube_clips(trending_topics: list[str], max_clips: int = 5) -> list[dict]:
    clips = []

    for topic in trending_topics[:3]:
        if len(clips) >= max_clips:
            break
        print(f"[YouTube] Searching for: {topic}")

        # Use ytsearch with delay and rotate queries slightly
        search_url = f"ytsearch3:{topic} short viral"
        entries = _ytdlp_search(search_url)

        for entry in entries:
            if len(clips) >= max_clips:
                break
            video_url = entry.get("url") or entry.get("webpage_url", "")
            if not video_url:
                continue
            # Ensure full URL
            if not video_url.startswith("http"):
                video_url = f"https://www.youtube.com/watch?v={entry.get('id','')}"

            clip_path = _download_clip(video_url, source="youtube",
                                       title=entry.get("title", ""))
            if clip_path:
                clips.append({
                    "path": str(clip_path),
                    "title": entry.get("title", ""),
                    "source": "youtube",
                    "topic": topic,
                    "score": entry.get("view_count", 0),
                    "url": video_url,
                    "description": (entry.get("description") or "")[:300],
                })

        time.sleep(random.uniform(3.0, 6.0))  # avoid 429

    print(f"[YouTube] Downloaded {len(clips)} clips")
    return clips


def _ytdlp_search(search_url: str) -> list[dict]:
    """Extract video metadata using yt-dlp without downloading."""
    cmd = [
        "yt-dlp",
        "--dump-json",
        "--no-download",
        "--no-playlist",
        "--match-filter", "duration <= 90",
        "--extractor-args", "youtube:skip=dash,hls",
        "--sleep-requests", "2",
        "--quiet",
        search_url,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
        entries = []
        for line in result.stdout.strip().split("\n"):
            if line.strip():
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return entries
    except Exception as e:
        print(f"[yt-dlp search] Error: {e}")
        return []


# ─────────────────────────────────────────────
# SHARED DOWNLOADER
# ─────────────────────────────────────────────

def _download_clip(url: str, source: str, title: str = "") -> Path | None:
    safe_title = re.sub(r'[^\w\s-]', '', title)[:35].strip().replace(" ", "_")
    filename = f"{source}_{safe_title}_{int(time.time())}"
    output_template = str(OUTPUT_DIR / f"{filename}.%(ext)s")

    cmd = [
        "yt-dlp",
        "--format", "bestvideo[ext=mp4][height<=720]+bestaudio[ext=m4a]/best[ext=mp4][height<=720]/best[height<=720]/best",
        "--merge-output-format", "mp4",
        "--max-filesize", "80m",
        "--output", output_template,
        "--no-playlist",
        "--sleep-requests", "1",
        "--retries", "3",
        "--quiet",
        "--no-warnings",
        url,
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=150)
        for f in OUTPUT_DIR.glob(f"{filename}*.mp4"):
            print(f"[Download] ✓ {f.name}")
            return f
        # Also check without extension assumption
        for f in OUTPUT_DIR.glob(f"{filename}*"):
            if f.stat().st_size > 10000:
                print(f"[Download] ✓ {f.name}")
                return f
        if result.stderr:
            print(f"[Download] ✗ {url[:60]}: {result.stderr[:150]}")
        return None
    except subprocess.TimeoutExpired:
        print(f"[Download] Timeout: {url[:60]}")
        return None
    except Exception as e:
        print(f"[Download] Error: {e}")
        return None


def _is_video_url(url: str) -> bool:
    domains = ["v.redd.it", "youtube.com", "youtu.be",
               "streamable.com", "gfycat.com", "redgifs.com"]
    return any(d in url for d in domains)


def fetch_all_clips(trending_topics: list[str], max_total: int = 8) -> list[dict]:
    per_source = max(2, max_total // 2)

    reddit_clips = fetch_reddit_clips(trending_topics, max_clips=per_source)
    youtube_clips = fetch_youtube_clips(trending_topics, max_clips=per_source)

    all_clips = reddit_clips + youtube_clips
    all_clips.sort(key=lambda x: x.get("score", 0), reverse=True)

    print(f"[Fetcher] Total clips ready: {len(all_clips)}")
    return all_clips[:max_total]
