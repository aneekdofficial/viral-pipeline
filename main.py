"""
main.py
Master orchestrator for the Viral Shorts Pipeline.
"""

import os
import sys
import json
import time
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent / "src"))

from trends_fetcher import get_trending_topics
from clip_fetcher import fetch_all_clips
from transcript_extractor import batch_extract_transcripts
from content_generator import batch_generate_content
from video_editor import batch_process_clips

CONFIG = {
    "geo": os.environ.get("PIPELINE_GEO", "US"),
    "max_clips": int(os.environ.get("PIPELINE_MAX_CLIPS", "5")),
    "top_trending_topics": 10,
    "crop_to_shorts": True,
    "output_dir": "output/final",
    "save_run_log": True,
}


def check_env():
    missing = []
    if not os.environ.get("GROQ_API_KEY"):
        missing.append("GROQ_API_KEY")
    if missing:
        print(f"[Main] ✗ Missing required env vars: {', '.join(missing)}")
        sys.exit(1)
    print("[Main] ✓ All environment variables found")


def run_pipeline():
    run_start = time.time()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    print("\n" + "="*60)
    print("   VIRAL SHORTS PIPELINE")
    print(f"   Run: {timestamp}")
    print("="*60 + "\n")

    # Step 1: Trends
    print("── Step 1/5: Fetching Google Trends ──")
    trending_topics = get_trending_topics(geo=CONFIG["geo"], top_n=CONFIG["top_trending_topics"])
    print(f"  Topics: {', '.join(trending_topics[:5])}\n")

    # Step 2: Clips (with retry)
    print("── Step 2/5: Fetching viral clips ──")
    clips = fetch_all_clips(trending_topics=trending_topics, max_total=CONFIG["max_clips"])

    if not clips:
        print("[Main] ⚠ First attempt got 0 clips, retrying with broader topics...")
        time.sleep(5)
        broad_topics = ["funny", "amazing", "viral", "shocking", "unexpected"]
        clips = fetch_all_clips(trending_topics=broad_topics, max_total=CONFIG["max_clips"])

    if not clips:
        print("[Main] ✗ Could not fetch any clips after retry. Exiting.")
        sys.exit(1)

    print(f"  Fetched {len(clips)} clips\n")

    # Step 3: Transcripts
    print("── Step 3/5: Extracting transcripts ──")
    clips = batch_extract_transcripts(clips)
    print(f"  Transcripts done\n")

    # Step 4: LLM content
    print("── Step 4/5: Generating content with Groq LLM ──")
    clips = batch_generate_content(clips, trending_topics)
    print(f"  Content generated\n")

    # Step 5: Video editing
    print("── Step 5/5: Editing videos with FFmpeg ──")
    output_paths = batch_process_clips(clips=clips, crop_to_shorts=CONFIG["crop_to_shorts"])

    elapsed = time.time() - run_start
    print("\n" + "="*60)
    print(f"   PIPELINE COMPLETE")
    print(f"   ✓ {len(output_paths)}/{len(clips)} clips processed")
    print(f"   ⏱  {elapsed:.1f}s total")
    print("="*60)
    for p in output_paths:
        print(f"   → {Path(p).name}")

    if CONFIG["save_run_log"]:
        log = {
            "timestamp": timestamp,
            "trending_topics": trending_topics,
            "clips_fetched": len(clips),
            "clips_processed": len(output_paths),
            "elapsed_seconds": round(elapsed, 1),
            "outputs": [Path(p).name for p in output_paths],
        }
        log_path = Path("output") / f"run_log_{timestamp}.json"
        log_path.parent.mkdir(exist_ok=True)
        log_path.write_text(json.dumps(log, indent=2))
        print(f"\n   📋 Log: {log_path}")

    return output_paths


if __name__ == "__main__":
    check_env()
    run_pipeline()
