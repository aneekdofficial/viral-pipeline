# 🎬 Viral Shorts Pipeline

A fully automated, **100% free** pipeline that:
1. Fetches currently trending topics from **Google Trends**
2. Downloads viral clips from **Reddit** (via SocialGrep) + **YouTube** (via yt-dlp)
3. Extracts transcripts for context
4. Generates **hook text, commentary, title & hashtags** using **Groq LLM**
5. Burns text overlays onto clips using **FFmpeg**
6. Outputs ready-to-post `.mp4` files in 9:16 Shorts format

Runs automatically every day via **GitHub Actions** — zero server cost.

---

## 📁 Project Structure

```
viral-pipeline/
├── main.py                          # Master orchestrator
├── src/
│   ├── trends_fetcher.py            # Google Trends via pytrends
│   ├── clip_fetcher.py              # Reddit (SocialGrep) + YouTube (yt-dlp)
│   ├── transcript_extractor.py      # Subtitle extraction via yt-dlp
│   ├── content_generator.py         # Groq LLM → hook text, title, hashtags
│   └── video_editor.py              # FFmpeg text overlays + 9:16 crop
├── .github/
│   └── workflows/
│       └── pipeline.yml             # GitHub Actions daily schedule
├── requirements.txt
└── README.md
```

---

## ⚙️ Setup

### 1. Fork / Push this repo to GitHub

### 2. Add GitHub Secrets
Go to: `Repo → Settings → Secrets and Variables → Actions → New repository secret`

| Secret Name | Value |
|---|---|
| `GROQ_API_KEY` | Your Groq API key |
| `RAPIDAPI_KEY` | Your RapidAPI key (for SocialGrep) |

### 3. Enable GitHub Actions
Go to the **Actions** tab in your repo and enable workflows.

### 4. Run manually or wait for daily schedule
- **Manual:** Actions tab → "Viral Shorts Pipeline" → "Run workflow"
- **Scheduled:** Runs daily at 9:00 AM UTC (2:30 PM IST)

---

## 📦 Downloading Your Clips

After each run:
1. Go to **Actions** tab
2. Click the latest workflow run
3. Scroll to **Artifacts** at the bottom
4. Download `viral-clips-{run_number}` — contains all `.mp4` and `.txt` files

Each clip comes with a companion `.txt` file containing:
- Viral title
- Social media caption
- Full hashtag set
- Text overlay breakdown

---

## 🧩 How It Works

### Google Trends → Clip Selection
`pytrends` fetches today's top 10 trending search topics. These are used to:
- Search Reddit for matching viral video posts
- Search YouTube Shorts for matching content
- Inform the LLM what's culturally relevant today

### SocialGrep → Reddit Clips
SocialGrep's RapidAPI endpoint searches viral subreddits:
- `r/nextfuckinglevel`, `r/PublicFreakout`, `r/maybemaybemaybe`, etc.
- Returns posts sorted by upvotes
- `yt-dlp` downloads the actual video from `v.redd.it` links

### Groq LLM → Content Generation
`llama3-70b-8192` generates for each clip:
- **Hook text** — shown 0–2.5s, creates immediate curiosity
- **Mid-clip texts** — commentary at ~30% and ~60% of clip duration
- **End CTA** — shown in last 3 seconds
- **Viral title** — 60 char max, optimized for clicks
- **8 hashtags** — mix of trending + niche + broad reach
- **Caption** — conversational 2-3 sentence social post

### FFmpeg → Video Editing
Text overlays are burned with:
- White bold text, black 3px stroke (classic viral style)
- Smooth 0.3s fade in/out on each text block
- 9:16 crop + pad to black for Shorts format
- Fast H.264 encode, AAC audio, mobile-optimized

---

## 🔧 Local Development

```bash
# Clone the repo
git clone https://github.com/aneekdofficial/viral-pipeline
cd viral-pipeline

# Install dependencies
pip install -r requirements.txt
pip install yt-dlp

# Install FFmpeg (Ubuntu/Mac)
sudo apt install ffmpeg   # Ubuntu
brew install ffmpeg       # Mac

# Set env vars
export GROQ_API_KEY=your_key_here
export RAPIDAPI_KEY=your_key_here

# Run
python main.py
```

---

## 📊 GitHub Actions Free Tier

| Resource | Limit | Our Usage |
|---|---|---|
| Minutes/month | 2,000 | ~5–8 min/run × 30 = ~200 min |
| Storage (artifacts) | 500 MB | ~50 MB/run (7-day retention) |
| Runs/month | Unlimited | 30 (daily) |

Well within free limits.

---

## 🛠 Customization

Edit `CONFIG` in `main.py`:

```python
CONFIG = {
    "geo": "IN",          # Change to India trends
    "max_clips": 3,        # Fewer clips = faster runs
    "crop_to_shorts": True # Set False for landscape output
}
```

---

## 📝 License
MIT — use freely, credit appreciated.
