"""
clip_fetcher.py
Fetches viral video clips from:
  - Reddit (via SocialGrep RapidAPI) → downloads with yt-dlp
  - YouTube Trending (via yt-dlp directly)

Filters clips by relevance to trending topics.
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

# Subreddits known for viral video content
VIRAL_SUBREDDITS = [
    "r/nextfuckinglevel",
    "r/PublicFreakout",
    "r/maybemaybemaybe",
    "r/therewasanattempt",
    "r/instant_regret",
    "r/unexpected",
    "r/interestingasfuck",
    "r/oddlysatisfying",
    "r/holdmyfeedingtube",
    "r/Whatcouldgowrong",
]


# ─────────────────────────────────────────────
# REDDIT via SocialGrep
# ─────────────────────────────────────────────

def fetch_reddit_clips(trending_topics: list[str], max_clips: int = 5) -> list[dict]:
    """
    Search SocialGrep for viral Reddit video posts matching trending topics.
    Downloads the actual video files using yt-dlp.
    
    Returns list of clip metadata dicts.
    """
    clips = []
    
    for topic in trending_topics[:3]:  # limit API calls
        print(f"[Reddit] Searching for: {topic}")
        posts = _socialgrep_search(topic)
        
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
                    "topic": topic,
                    "score": post.get("score", 0),
                    "url": url,
                })
        
        time.sleep(random.uniform(1.0, 2.0))  # polite delay between API calls
    
    print(f"[Reddit] Downloaded {len(clips)} clips")
    return clips


def _socialgrep_search(query: str, limit: int = 10) -> list[dict]:
    """Call SocialGrep API and return list of post dicts."""
    # Build subreddit + topic query
    sub_filter = ",".join(random.sample(VIRAL_SUBREDDITS, 3))
    full_query = f"{sub_filter},{query}"
    
    url = "https://socialgrep.p.rapidapi.com/search/posts"
    headers = {
        "Content-Type": "application/json",
        "x-rapidapi-host": "socialgrep.p.rapidapi.com",
        "x-rapidapi-key": RAPIDAPI_KEY,
    }
    params = {"query": full_query}
    
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        posts = data.get("data", [])
        
        # Sort by score (upvotes) descending
        posts.sort(key=lambda x: x.get("score", 0), reverse=True)
        return posts[:limit]
    
    except Exception as e:
        print(f"[SocialGrep] Error: {e}")
        return []


# ─────────────────────────────────────────────
# YOUTUBE TRENDING via yt-dlp
# ─────────────────────────────────────────────

def fetch_youtube_clips(trending_topics: list[str], max_clips: int = 5) -> list[dict]:
    """
    Fetch viral clips from YouTube Shorts trending feed.
    Uses yt-dlp with no API key.
    
    Returns list of clip metadata dicts.
    """
    clips = []
    
    # Try YouTube Shorts trending
    sources = [
        "https://www.youtube.com/feed/trending?bp=4gINGgt5dFBpZGJvYXJkcw%3D%3D",  # Shorts shelf
        "https://www.youtube.com/feed/trending",
    ]
    
    for topic in trending_topics[:2]:
        if len(clips) >= max_clips:
            break
        
        print(f"[YouTube] Searching Shorts for: {topic}")
        search_url = f"ytsearch5:{topic} shorts"
        
        info = _ytdlp_extract_info(search_url, max_duration=90)
        
        for entry in info:
            if len(clips) >= max_clips:
                break
            
            video_url = entry.get("webpage_url", "")
            if not video_url:
                continue
            
            clip_path = _download_clip(video_url, source="youtube", title=entry.get("title", ""))
            if clip_path:
                clips.append({
                    "path": str(clip_path),
                    "title": entry.get("title", ""),
                    "source": "youtube",
                    "topic": topic,
                    "score": entry.get("view_count", 0),
                    "url": video_url,
                    "description": entry.get("description", "")[:500],
                })
    
    print(f"[YouTube] Downloaded {len(clips)} clips")
    return clips


def _ytdlp_extract_info(url: str, max_duration: int = 90) -> list[dict]:
    """Use yt-dlp to extract metadata without downloading."""
    cmd = [
        "yt-dlp",
        "--dump-json",
        "--no-download",
        "--match-filter", f"duration <= {max_duration}",
        "--flat-playlist",
        url
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        entries = []
        for line in result.stdout.strip().split("\n"):
            if line.strip():
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return entries
    except Exception as e:
        print(f"[yt-dlp extract] Error: {e}")
        return []


# ─────────────────────────────────────────────
# SHARED DOWNLOADER
# ─────────────────────────────────────────────

def _download_clip(url: str, source: str, title: str = "") -> Path | None:
    """
    Download a video clip using yt-dlp.
    Returns path to downloaded file, or None if failed.
    """
    safe_title = re.sub(r'[^\w\s-]', '', title)[:40].strip().replace(" ", "_")
    filename = f"{source}_{safe_title}_{int(time.time())}"
    output_path = OUTPUT_DIR / f"{filename}.%(ext)s"
    
    cmd = [
        "yt-dlp",
        "--format", "bestvideo[ext=mp4][height<=720]+bestaudio[ext=m4a]/best[ext=mp4][height<=720]/best",
        "--merge-output-format", "mp4",
        "--max-filesize", "100m",
        "--output", str(output_path),
        "--no-playlist",
        "--quiet",
        url
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        
        # Find the actual output file
        for f in OUTPUT_DIR.glob(f"{filename}*"):
            if f.suffix == ".mp4":
                print(f"[Download] ✓ {f.name}")
                return f
        
        print(f"[Download] ✗ Failed for {url}: {result.stderr[:200]}")
        return None
    
    except subprocess.TimeoutExpired:
        print(f"[Download] Timeout for {url}")
        return None
    except Exception as e:
        print(f"[Download] Error: {e}")
        return None


def _is_video_url(url: str) -> bool:
    """Check if URL is likely a downloadable video."""
    video_domains = ["v.redd.it", "youtube.com", "youtu.be", "streamable.com", "imgur.com"]
    return any(domain in url for domain in video_domains)


def fetch_all_clips(trending_topics: list[str], max_total: int = 8) -> list[dict]:
    """
    Fetch clips from all sources, combined and deduplicated.
    """
    per_source = max_total // 2
    
    reddit_clips = fetch_reddit_clips(trending_topics, max_clips=per_source)
    youtube_clips = fetch_youtube_clips(trending_topics, max_clips=per_source)
    
    all_clips = reddit_clips + youtube_clips
    
    # Sort by score/views
    all_clips.sort(key=lambda x: x.get("score", 0), reverse=True)
    
    print(f"[Fetcher] Total clips ready: {len(all_clips)}")
    return all_clips[:max_total]


if __name__ == "__main__":
    test_topics = ["viral moment", "unbelievable", "shocking"]
    clips = fetch_youtube_clips(test_topics, max_clips=2)
    for c in clips:
        print(f"  [{c['source']}] {c['title'][:60]} → {c['path']}")
