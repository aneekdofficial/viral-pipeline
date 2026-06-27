"""
transcript_extractor.py
Extracts transcripts/subtitles from downloaded clips or their source URLs.
Falls back to auto-generated subtitles via yt-dlp.
Used to give the LLM context about what's actually in the clip.
"""

import os
import re
import json
import subprocess
from pathlib import Path


TRANSCRIPT_DIR = Path("output/transcripts")
TRANSCRIPT_DIR.mkdir(parents=True, exist_ok=True)


def extract_transcript(clip_meta: dict) -> str:
    """
    Extract transcript text for a clip.
    Tries multiple methods in order:
      1. yt-dlp auto-subtitles from source URL
      2. yt-dlp manual subtitles
      3. Fallback: use title + description as context
    
    Args:
        clip_meta: dict with keys: url, title, description, path
    
    Returns:
        Transcript string (may be empty if all methods fail)
    """
    url = clip_meta.get("url", "")
    title = clip_meta.get("title", "")
    description = clip_meta.get("description", "")
    
    # Method 1: Try yt-dlp subtitles from URL
    if url:
        transcript = _fetch_subtitles_ytdlp(url)
        if transcript and len(transcript.strip()) > 30:
            print(f"[Transcript] ✓ Got subtitles for: {title[:40]}")
            return transcript
    
    # Method 2: Use title + description as context (always works)
    context = _build_context_from_meta(title, description)
    print(f"[Transcript] Using metadata context for: {title[:40]}")
    return context


def _fetch_subtitles_ytdlp(url: str) -> str:
    """
    Download auto-generated subtitles from yt-dlp and parse them.
    Returns cleaned plain text transcript.
    """
    subtitle_path = TRANSCRIPT_DIR / f"sub_{abs(hash(url))}"
    
    cmd = [
        "yt-dlp",
        "--write-auto-sub",
        "--write-sub",
        "--sub-lang", "en",
        "--sub-format", "vtt",
        "--skip-download",
        "--output", str(subtitle_path),
        "--quiet",
        url
    ]
    
    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        # Look for the downloaded subtitle file
        for f in TRANSCRIPT_DIR.glob(f"sub_{abs(hash(url))}*.vtt"):
            text = _parse_vtt(f)
            f.unlink()  # clean up
            return text
        
        # Also try .en.vtt pattern
        for f in TRANSCRIPT_DIR.glob(f"sub_{abs(hash(url))}*"):
            if f.suffix in [".vtt", ".srt"]:
                text = _parse_vtt(f) if f.suffix == ".vtt" else _parse_srt(f)
                f.unlink()
                return text
        
        return ""
    
    except subprocess.TimeoutExpired:
        return ""
    except Exception as e:
        print(f"[Transcript] Subtitle fetch error: {e}")
        return ""


def _parse_vtt(filepath: Path) -> str:
    """Parse WebVTT subtitle file into plain text."""
    try:
        content = filepath.read_text(encoding="utf-8", errors="ignore")
        lines = content.split("\n")
        text_lines = []
        
        for line in lines:
            line = line.strip()
            # Skip VTT header, timestamps, and empty lines
            if (not line or 
                line.startswith("WEBVTT") or 
                "-->" in line or 
                re.match(r'^\d+$', line) or
                line.startswith("NOTE") or
                line.startswith("STYLE")):
                continue
            
            # Remove HTML tags (like <c>, <b>, etc.)
            clean = re.sub(r'<[^>]+>', '', line)
            clean = re.sub(r'&amp;', '&', clean)
            clean = re.sub(r'&lt;', '<', clean)
            clean = re.sub(r'&gt;', '>', clean)
            
            if clean.strip():
                text_lines.append(clean.strip())
        
        # Deduplicate consecutive repeated lines (common in auto-subs)
        deduped = []
        prev = ""
        for line in text_lines:
            if line != prev:
                deduped.append(line)
                prev = line
        
        return " ".join(deduped)
    
    except Exception as e:
        print(f"[Transcript] VTT parse error: {e}")
        return ""


def _parse_srt(filepath: Path) -> str:
    """Parse SRT subtitle file into plain text."""
    try:
        content = filepath.read_text(encoding="utf-8", errors="ignore")
        # Remove timing lines, sequence numbers, and HTML tags
        clean = re.sub(r'\d+\n\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}\n', '', content)
        clean = re.sub(r'<[^>]+>', '', clean)
        clean = re.sub(r'\n+', ' ', clean).strip()
        return clean
    except Exception:
        return ""


def _build_context_from_meta(title: str, description: str) -> str:
    """Build a context string from video metadata when transcript isn't available."""
    parts = []
    if title:
        parts.append(f"Video title: {title}")
    if description:
        # Trim description to first 300 chars
        desc_preview = description[:300].strip()
        if desc_preview:
            parts.append(f"Description: {desc_preview}")
    
    return "\n".join(parts)


def batch_extract_transcripts(clips: list[dict]) -> list[dict]:
    """
    Add transcript field to each clip in the list.
    Returns updated clips list.
    """
    for clip in clips:
        clip["transcript"] = extract_transcript(clip)
    return clips


if __name__ == "__main__":
    test_clip = {
        "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "title": "Test Video",
        "description": "A test description",
        "path": ""
    }
    result = extract_transcript(test_clip)
    print(f"Transcript preview: {result[:200]}")
