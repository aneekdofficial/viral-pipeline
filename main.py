"""
main.py
Master orchestrator for the Viral Shorts Pipeline.

Flow:
  1. Fetch trending topics from Google Trends
  2. Fetch viral clips from Reddit (SocialGrep) + YouTube (yt-dlp)
  3. Extract transcripts for each clip
  4. Generate hook text, title, hashtags via Groq LLM
  5. Burn text overlays onto clips via FFmpeg
  6. Save final .mp4 + metadata .txt files

Run locally:  python main.py
Run on CI:    triggered by GitHub Actions on schedule
"""

import os
import sys
import json
import time
import shutil
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from trends_fetcher import get_trending_topics
from clip_fetcher import fetch_all_clips
from transcript_extractor import batch_extract_transcripts
from content_generator import batch_generate_content
from video_editor import batch_process_clips


# ── Config ──────────────────────────────────────────────────────────────────
CONFIG = {
    "geo": "US",                    # Google Trends country
    "max_clips": 5,                 # Max clips to process per run
    "top_trending_topics": 10,      # How many trending topics to fetch
    "crop_to_shorts": True,         # Crop output to 9:16 (Shorts format)
    "output_dir": "output/final",   # Final .mp4 output directory
    "save_run_log": True,           # Save a JSON log of each run
}
# ────────────────────────────────────────────────────────────────────────────


def check_env():
    """Verify required environment variables are set."""
    missing = []
    
    if not os.environ.get("GROQ_API_KEY"):
        missing.append("GROQ_API_KEY")
    if not os.environ.get("RAPIDAPI_KEY"):
        missing.append("RAPIDAPI_KEY")
    
    if missing:
        print(f"[Main] ⚠️  Missing env vars: {', '.join(missing)}")
        print("[Main] Set them as GitHub Secrets or in your .env file")
        if "GROQ_API_KEY" in missing:
            print("[Main] ✗ GROQ_API_KEY is required. Exiting.")
            sys.exit(1)
        else:
            print("[Main] Continuing without RAPIDAPI_KEY (Reddit clips will be skipped)")
    else:
        print("[Main] ✓ All environment variables found")


def run_pipeline():
    """Execute the full viral shorts pipeline."""
    run_start = time.time()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    print("\n" + "="*60)
    print("   VIRAL SHORTS PIPELINE")
    print(f"   Run: {timestamp}")
    print("="*60 + "\n")
    
    # ── Step 1: Google Trends ────────────────────────────────────────────
    print("── Step 1/5: Fetching Google Trends ──")
    trending_topics = get_trending_topics(
        geo=CONFIG["geo"],
        top_n=CONFIG["top_trending_topics"]
    )
    print(f"  Trending now: {', '.join(trending_topics[:5])}\n")
    
    # ── Step 2: Fetch Clips ──────────────────────────────────────────────
    print("── Step 2/5: Fetching viral clips ──")
    clips = fetch_all_clips(
        trending_topics=trending_topics,
        max_total=CONFIG["max_clips"]
    )
    
    if not clips:
        print("[Main] ✗ No clips fetched. Exiting.")
        sys.exit(1)
    
    print(f"  Fetched {len(clips)} clips\n")
    
    # ── Step 3: Extract Transcripts ──────────────────────────────────────
    print("── Step 3/5: Extracting transcripts ──")
    clips = batch_extract_transcripts(clips)
    print(f"  Transcripts ready for {len(clips)} clips\n")
    
    # ── Step 4: Generate Content via LLM ────────────────────────────────
    print("── Step 4/5: Generating viral content with Groq LLM ──")
    clips = batch_generate_content(clips, trending_topics)
    print(f"  Content generated for {len(clips)} clips\n")
    
    # ── Step 5: Edit Videos ──────────────────────────────────────────────
    print("── Step 5/5: Editing videos with FFmpeg ──")
    output_paths = batch_process_clips(
        clips=clips,
        crop_to_shorts=CONFIG["crop_to_shorts"]
    )
    
    # ── Summary ──────────────────────────────────────────────────────────
    elapsed = time.time() - run_start
    success_count = len(output_paths)
    
    print("\n" + "="*60)
    print(f"   PIPELINE COMPLETE")
    print(f"   ✓ {success_count}/{len(clips)} clips processed successfully")
    print(f"   ⏱  Total time: {elapsed:.1f}s")
    print(f"   📁 Output: {CONFIG['output_dir']}/")
    print("="*60)
    
    for p in output_paths:
        print(f"   → {Path(p).name}")
    
    # ── Save run log ─────────────────────────────────────────────────────
    if CONFIG["save_run_log"]:
        log = {
            "timestamp": timestamp,
            "trending_topics": trending_topics,
            "clips_fetched": len(clips),
            "clips_processed": success_count,
            "elapsed_seconds": round(elapsed, 1),
            "outputs": [Path(p).name for p in output_paths],
            "clip_details": [
                {
                    "title": c.get("title", ""),
                    "source": c.get("source", ""),
                    "topic": c.get("topic", ""),
                    "viral_title": c.get("content", {}).get("viral_title", ""),
                    "hashtags": c.get("content", {}).get("hashtags", []),
                }
                for c in clips
            ]
        }
        
        log_path = Path("output") / f"run_log_{timestamp}.json"
        log_path.parent.mkdir(exist_ok=True)
        log_path.write_text(json.dumps(log, indent=2))
        print(f"\n   📋 Run log saved: {log_path}")
    
    return output_paths


if __name__ == "__main__":
    check_env()
    run_pipeline()
