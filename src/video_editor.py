"""
video_editor.py
Uses FFmpeg to process clips and burn text overlays.

Applies:
  - Hook text (0s - 2.5s) — large, centered, white bold
  - Mid-clip texts — smaller, lower-third style  
  - End CTA text (last 3s) — centered, animated fade
  - Viral title card (first frame metadata)
  - 9:16 crop for Shorts format (optional)

All text is styled like viral Shorts — white text, black stroke, bold.
"""

import os
import re
import subprocess
import shutil
from pathlib import Path


OUTPUT_DIR = Path("output/final")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Font path - will use system default if not found
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FALLBACK_FONT = "DejaVuSans-Bold"


def process_clip(clip_meta: dict, content: dict, crop_to_shorts: bool = True) -> str | None:
    """
    Full video processing pipeline for one clip.
    
    Args:
        clip_meta: dict with 'path', 'title'
        content: dict from content_generator with hook_text, mid_texts, end_text
        crop_to_shorts: if True, crop/pad to 9:16 aspect ratio
    
    Returns:
        Path to output .mp4 file, or None if failed
    """
    input_path = clip_meta.get("path", "")
    if not input_path or not Path(input_path).exists():
        print(f"[Editor] Input file not found: {input_path}")
        return None
    
    # Get video duration
    duration = _get_duration(input_path)
    if not duration:
        print(f"[Editor] Could not read duration for: {input_path}")
        return None
    
    print(f"[Editor] Processing clip: {Path(input_path).name} ({duration:.1f}s)")
    
    # Build output filename from viral title
    safe_title = re.sub(r'[^\w\s-]', '', content.get("viral_title", "clip"))
    safe_title = safe_title[:40].strip().replace(" ", "_")
    output_path = OUTPUT_DIR / f"{safe_title}_final.mp4"
    
    # Build FFmpeg filter chain
    filter_complex = _build_filter_complex(
        content=content,
        duration=duration,
        crop_to_shorts=crop_to_shorts,
    )
    
    cmd = [
        "ffmpeg", "-y",
        "-i", str(input_path),
        "-vf", filter_complex,
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "128k",
        "-movflags", "+faststart",
        str(output_path)
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0 and output_path.exists():
            size_mb = output_path.stat().st_size / (1024 * 1024)
            print(f"[Editor] ✓ Output: {output_path.name} ({size_mb:.1f} MB)")
            return str(output_path)
        else:
            print(f"[Editor] ✗ FFmpeg failed:\n{result.stderr[-500:]}")
            return None
    
    except subprocess.TimeoutExpired:
        print(f"[Editor] Timeout processing {input_path}")
        return None
    except Exception as e:
        print(f"[Editor] Error: {e}")
        return None


def _build_filter_complex(content: dict, duration: float, crop_to_shorts: bool) -> str:
    """
    Build the FFmpeg -vf filter string for all text overlays.
    
    Text layers:
      1. Optional 9:16 crop/pad
      2. Hook text: 0s → 2.5s (or 20% of duration)
      3. Mid texts: at position_pct% of duration
      4. End text: last 3s
    """
    filters = []
    
    # Step 1: Crop to 9:16 for Shorts (1080x1920 or scale to fit)
    if crop_to_shorts:
        filters.append(
            "scale=1080:1920:force_original_aspect_ratio=decrease,"
            "pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black"
        )
    
    hook_text = content.get("hook_text", "")
    mid_texts = content.get("mid_texts", [])
    end_text = content.get("end_text", "")
    
    hook_end = min(2.5, duration * 0.2)
    end_start = max(duration - 3.0, duration * 0.8)
    
    # Step 2: Hook text — large, centered, top-ish
    if hook_text:
        filters.append(_drawtext(
            text=hook_text,
            fontsize=70,
            x="(w-text_w)/2",
            y="h*0.12",
            start=0,
            end=hook_end,
            style="bold_white",
        ))
    
    # Step 3: Mid-clip commentary texts
    for mt in mid_texts:
        t = mt.get("text", "")
        pct = mt.get("position_pct", 50) / 100.0
        t_start = duration * pct
        t_end = min(t_start + 2.5, duration - 0.5)
        
        if t and t_start < duration:
            filters.append(_drawtext(
                text=t,
                fontsize=55,
                x="(w-text_w)/2",
                y="h*0.82",
                start=t_start,
                end=t_end,
                style="bold_white",
            ))
    
    # Step 4: End CTA text — centered, bottom area
    if end_text and end_start < duration:
        filters.append(_drawtext(
            text=end_text,
            fontsize=60,
            x="(w-text_w)/2",
            y="h*0.88",
            start=end_start,
            end=duration,
            style="bold_yellow",
        ))
    
    return ",".join(filters) if filters else "null"


def _drawtext(
    text: str,
    fontsize: int,
    x: str,
    y: str,
    start: float,
    end: float,
    style: str = "bold_white",
) -> str:
    """
    Generate an FFmpeg drawtext filter string.
    
    Styles:
      bold_white  — white text, black border (classic viral style)
      bold_yellow — yellow text, black border (CTA style)
    """
    # Escape special characters for FFmpeg
    safe_text = (text
        .replace("\\", "\\\\")
        .replace("'", "\\'")
        .replace(":", "\\:")
        .replace("[", "\\[")
        .replace("]", "\\]")
        .replace(",", "\\,")
    )
    
    # Check if font file exists
    font_arg = f"fontfile={FONT_PATH}:" if Path(FONT_PATH).exists() else f"font={FALLBACK_FONT}:"
    
    if style == "bold_yellow":
        color = "yellow"
        border_color = "black"
    else:
        color = "white"
        border_color = "black"
    
    # Fade in/out effect using alpha
    alpha = (
        f"if(lt(t,{start}),0,"
        f"if(lt(t,{start+0.3}),(t-{start})/0.3,"
        f"if(lt(t,{end-0.3}),1,"
        f"if(lt(t,{end}),({end}-t)/0.3,0))))"
    )
    
    return (
        f"drawtext={font_arg}"
        f"text='{safe_text}':"
        f"fontsize={fontsize}:"
        f"fontcolor={color}:"
        f"borderw=3:"
        f"bordercolor={border_color}:"
        f"x={x}:"
        f"y={y}:"
        f"alpha='{alpha}'"
    )


def _get_duration(filepath: str) -> float | None:
    """Get video duration in seconds using ffprobe."""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        filepath
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        return float(result.stdout.strip())
    except Exception:
        return None


def save_metadata(clip_meta: dict, content: dict, output_path: str):
    """Save a .txt metadata file alongside the output video."""
    meta_path = Path(output_path).with_suffix(".txt")
    
    hashtags_str = " ".join([f"#{h}" for h in content.get("hashtags", [])])
    
    lines = [
        f"VIRAL TITLE: {content.get('viral_title', '')}",
        f"",
        f"CAPTION:",
        f"{content.get('caption', '')}",
        f"",
        f"HASHTAGS:",
        f"{hashtags_str}",
        f"",
        f"SOURCE: {clip_meta.get('url', '')}",
        f"ORIGINAL TITLE: {clip_meta.get('title', '')}",
        f"TRENDING TOPIC: {clip_meta.get('topic', '')}",
        f"",
        f"TEXT OVERLAYS:",
        f"  Hook: {content.get('hook_text', '')}",
    ]
    
    for mt in content.get("mid_texts", []):
        lines.append(f"  Mid ({mt.get('position_pct')}%): {mt.get('text', '')}")
    
    lines.append(f"  End CTA: {content.get('end_text', '')}")
    
    meta_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"[Editor] Metadata saved: {meta_path.name}")


def batch_process_clips(clips: list[dict], crop_to_shorts: bool = True) -> list[str]:
    """
    Process all clips with their generated content.
    Returns list of output file paths.
    """
    output_paths = []
    
    for i, clip in enumerate(clips, 1):
        content = clip.get("content")
        if not content:
            print(f"[Editor] Skipping clip {i} — no content generated")
            continue
        
        print(f"\n[Editor] Processing clip {i}/{len(clips)}")
        output_path = process_clip(clip, content, crop_to_shorts=crop_to_shorts)
        
        if output_path:
            save_metadata(clip, content, output_path)
            output_paths.append(output_path)
    
    return output_paths


if __name__ == "__main__":
    print("Video editor module loaded. Run main.py to process clips.")
