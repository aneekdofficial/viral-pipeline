"""
content_generator.py
Uses Groq API (llama3-70b) to generate:
  - Hook text (first 1-3 seconds overlay)
  - Mid-clip commentary text (with timestamps)
  - End CTA text
  - Viral title
  - Trending hashtags

All content is informed by Google Trends data + clip transcript.
"""

import os
import json
import re
from groq import Groq

client = Groq(api_key=os.environ.get("GROQ_API_KEY", ""))

MODEL = "llama3-70b-8192"


def generate_content(clip_meta: dict, trending_topics: list[str]) -> dict:
    """
    Generate all overlay text, title, and hashtags for a clip.
    
    Args:
        clip_meta: dict with keys: title, transcript, source, topic
        trending_topics: list of currently trending keyword strings
    
    Returns:
        dict with keys:
            hook_text, mid_texts (list), end_text,
            viral_title, hashtags (list), caption
    """
    transcript = clip_meta.get("transcript", "")
    title = clip_meta.get("title", "")
    topic = clip_meta.get("topic", "")
    source = clip_meta.get("source", "")
    
    trends_str = ", ".join(trending_topics[:8])
    
    prompt = f"""You are a viral short-form video editor who creates text overlays for YouTube Shorts and TikTok.

VIDEO INFO:
- Original title: {title}
- Source: {source}
- Matched trending topic: {topic}
- Transcript/context: {transcript[:800] if transcript else "Not available"}

CURRENTLY TRENDING ON GOOGLE: {trends_str}

Your job is to create engaging text overlays that make this clip go viral. Think about how the most viral Shorts are edited - they use:
- A shocking/curiosity-gap hook in the first 2 seconds
- Relatable commentary during the clip
- A strong CTA at the end

Generate the following and respond ONLY with valid JSON, no markdown, no explanation:

{{
  "hook_text": "A single punchy hook line (max 8 words) shown in first 2 seconds. Make it shocking, relatable, or curiosity-gap. Examples: 'Nobody expected this...', 'POV: You made the wrong choice', 'This changes everything'",
  
  "mid_texts": [
    {{
      "text": "Short commentary text (max 10 words)",
      "position_pct": 30
    }},
    {{
      "text": "Another reaction/commentary line (max 10 words)",  
      "position_pct": 60
    }}
  ],
  
  "end_text": "Strong CTA (max 8 words). Examples: 'Follow for more crazy moments', 'Tag someone who needs to see this'",
  
  "viral_title": "YouTube/TikTok title (max 60 chars, include numbers or power words if relevant, tie to trending topic if natural)",
  
  "hashtags": ["hashtag1", "hashtag2", "hashtag3", "hashtag4", "hashtag5", "hashtag6", "hashtag7", "hashtag8"],
  
  "caption": "2-3 sentence social media caption that's conversational and engaging"
}}

Rules:
- hook_text must create immediate curiosity or emotion
- mid_texts should feel like a friend reacting alongside the viewer  
- hashtags should mix: trending topic tags + niche tags + broad reach tags (no # symbol, just the word)
- viral_title should NOT be clickbait-y but SHOULD be compelling
- tie content to trending topics only if it feels natural, never forced
"""

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.85,
            max_tokens=800,
        )
        
        raw = response.choices[0].message.content.strip()
        
        # Clean potential markdown fences
        raw = re.sub(r'^```json\s*', '', raw)
        raw = re.sub(r'\s*```$', '', raw)
        
        result = json.loads(raw)
        
        # Validate and set defaults
        result.setdefault("hook_text", "You won't believe this...")
        result.setdefault("mid_texts", [{"text": "Wait for it...", "position_pct": 50}])
        result.setdefault("end_text", "Follow for more!")
        result.setdefault("viral_title", title[:60] if title else "Viral Moment")
        result.setdefault("hashtags", ["viral", "shorts", "fyp", "trending"])
        result.setdefault("caption", "What a moment! Drop a 🔥 if you agree.")
        
        print(f"[LLM] ✓ Generated content for: {title[:40]}")
        print(f"  Hook: {result['hook_text']}")
        print(f"  Title: {result['viral_title']}")
        print(f"  Tags: {' '.join(['#'+h for h in result['hashtags'][:4]])}")
        
        return result
    
    except json.JSONDecodeError as e:
        print(f"[LLM] JSON parse error: {e}. Using fallback content.")
        return _fallback_content(title, trending_topics)
    
    except Exception as e:
        print(f"[LLM] Generation error: {e}. Using fallback content.")
        return _fallback_content(title, trending_topics)


def _fallback_content(title: str, trending_topics: list[str]) -> dict:
    """Safe fallback if LLM call fails."""
    top_topic = trending_topics[0] if trending_topics else "viral"
    return {
        "hook_text": "You won't believe this...",
        "mid_texts": [
            {"text": "Wait for it...", "position_pct": 40},
            {"text": "Did that just happen?!", "position_pct": 70},
        ],
        "end_text": "Follow for more! 🔥",
        "viral_title": (title[:55] + "...") if len(title) > 55 else title,
        "hashtags": [
            top_topic.replace(" ", ""),
            "viral", "shorts", "fyp", "trending",
            "foryou", "mustwatch", "unexpected"
        ],
        "caption": f"This is wild! Related to what's trending: {top_topic}. Drop a 🔥 below!"
    }


def batch_generate_content(clips: list[dict], trending_topics: list[str]) -> list[dict]:
    """
    Add generated content to each clip in the list.
    Returns updated clips list.
    """
    for clip in clips:
        clip["content"] = generate_content(clip, trending_topics)
    return clips


if __name__ == "__main__":
    test_clip = {
        "title": "Guy slips on banana peel in front of judge",
        "transcript": "The defendant walked into the courtroom confidently but slipped...",
        "source": "reddit",
        "topic": "courtroom fail"
    }
    test_trends = ["courtroom drama", "viral fails", "unexpected moments"]
    result = generate_content(test_clip, test_trends)
    print(json.dumps(result, indent=2))
