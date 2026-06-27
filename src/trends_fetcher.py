"""
trends_fetcher.py
Fetches trending topics via multiple fallback methods:
  1. pytrends realtime trending searches
  2. pytrends daily trending (different endpoint)
  3. Hardcoded evergreen viral topics (last resort)
"""

import time
import random


def get_trending_topics(geo: str = "US", top_n: int = 10) -> list[str]:
    """
    Fetch top trending topics. Tries multiple methods with fallbacks.
    """
    # Method 1: pytrends realtime
    topics = _try_realtime_trends(geo, top_n)
    if topics:
        print(f"[Trends] ✓ Got {len(topics)} realtime trending topics")
        return topics

    # Method 2: pytrends top charts
    topics = _try_top_charts(geo, top_n)
    if topics:
        print(f"[Trends] ✓ Got {len(topics)} top chart topics")
        return topics

    # Method 3: evergreen fallback
    print("[Trends] Using evergreen fallback topics")
    return _evergreen_topics()[:top_n]


def _try_realtime_trends(geo: str, top_n: int) -> list[str]:
    try:
        from pytrends.request import TrendReq
        pt = TrendReq(hl="en-US", tz=360, timeout=(10, 25),
                      retries=1, backoff_factor=0.5)
        df = pt.realtime_trending_searches(pn=_to_pn(geo))
        if df is not None and not df.empty:
            col = df.columns[0]
            return df[col].dropna().tolist()[:top_n]
    except Exception as e:
        print(f"[Trends] Realtime failed: {e}")
    return []


def _try_top_charts(geo: str, top_n: int) -> list[str]:
    try:
        from pytrends.request import TrendReq
        pt = TrendReq(hl="en-US", tz=360, timeout=(10, 25),
                      retries=1, backoff_factor=0.5)
        df = pt.trending_searches(pn=_to_pn(geo))
        if df is not None and not df.empty:
            return df[0].dropna().tolist()[:top_n]
    except Exception as e:
        print(f"[Trends] Top charts failed: {e}")
    return []


def _to_pn(geo: str) -> str:
    mapping = {
        "US": "united_states", "IN": "india",
        "GB": "united_kingdom", "CA": "canada", "AU": "australia",
    }
    return mapping.get(geo.upper(), "united_states")


def _evergreen_topics() -> list[str]:
    return [
        "viral moment", "unexpected", "shocking", "unbelievable",
        "funny fail", "wholesome", "incredible skill", "caught on camera",
        "you won't believe", "satisfying", "genius hack", "wild animal",
        "amazing rescue", "close call", "instant karma"
    ]
