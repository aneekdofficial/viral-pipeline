"""
trends_fetcher.py
Fetches currently trending topics from Google Trends using pytrends.
Returns a ranked list of trending keywords to guide clip selection.
"""

import time
import random
from pytrends.request import TrendReq


def get_trending_topics(geo: str = "US", top_n: int = 10) -> list[str]:
    """
    Fetch top trending search topics from Google Trends.
    
    Args:
        geo: Country code (US, IN, GB, etc.)
        top_n: How many trending topics to return
    
    Returns:
        List of trending keyword strings
    """
    try:
        pytrends = TrendReq(hl="en-US", tz=360, timeout=(10, 25))
        
        # Get daily trending searches
        trending_df = pytrends.trending_searches(pn=_country_to_pn(geo))
        
        topics = trending_df[0].tolist()[:top_n]
        print(f"[Trends] Fetched {len(topics)} trending topics for {geo}")
        return topics

    except Exception as e:
        print(f"[Trends] Warning: Could not fetch trends ({e}). Using fallback topics.")
        return _fallback_topics()


def get_trending_topics_with_scores(geo: str = "US", top_n: int = 10) -> list[dict]:
    """
    Returns trending topics with their relative interest scores.
    
    Returns:
        List of dicts: [{"topic": str, "score": int (0-100)}, ...]
    """
    topics = get_trending_topics(geo=geo, top_n=top_n)
    
    if not topics:
        return []

    try:
        pytrends = TrendReq(hl="en-US", tz=360, timeout=(10, 25))
        
        # Score in batches of 5 (pytrends limit)
        scored = []
        batch = topics[:5]
        
        pytrends.build_payload(batch, timeframe="now 1-d", geo=geo)
        time.sleep(random.uniform(1.5, 3.0))  # polite delay
        interest_df = pytrends.interest_over_time()
        
        for topic in topics:
            if topic in interest_df.columns:
                score = int(interest_df[topic].mean())
            else:
                score = 50  # default mid-score if not found
            scored.append({"topic": topic, "score": score})
        
        # Sort by score descending
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored

    except Exception as e:
        print(f"[Trends] Score fetch failed ({e}). Returning unscored topics.")
        return [{"topic": t, "score": 50} for t in topics]


def _country_to_pn(geo: str) -> str:
    """Map ISO country code to pytrends pn parameter."""
    mapping = {
        "US": "united_states",
        "IN": "india",
        "GB": "united_kingdom",
        "CA": "canada",
        "AU": "australia",
    }
    return mapping.get(geo.upper(), "united_states")


def _fallback_topics() -> list[str]:
    """Fallback trending topics if pytrends fails."""
    return [
        "viral video", "shocking moment", "unbelievable", 
        "crazy reaction", "must watch", "unexpected", 
        "incredible", "funny fail", "wholesome", "breaking news"
    ]


if __name__ == "__main__":
    print("Testing trends fetcher...")
    topics = get_trending_topics(geo="US", top_n=10)
    for i, t in enumerate(topics, 1):
        print(f"  {i}. {t}")
