# Joyun Competitive Intelligence System 

```
All Rights Reserved
```
Automated daily competitive intelligence for Joyun (Indian skincare brand).
**Using Claude API / Gemini API + GitHub Actions.**

## Pipeline

```
GitHub Actions (1:30 UTC daily = 7:00 AM IST)
   │
   ├── run_intel.py     → Claude API w/ web_search → CSV + report + dashboard
   ├── send_telegram.py → text summary + CSV + HTML to @joyunplix_bot
   └── git push         → preserves daily history in the repo
```

## One-time setup

### 1. Create the GitHub repo
```bash
git init
git add .
git commit -m "Initial Joyun intel system"
gh repo create joyun-intel --private --source=. --push
```

### 2. Add 3 secrets in GitHub
Settings → Secrets and variables → Actions → New repository secret:

| Name                  | Value |
|-----------------------|-------|
| `ANTHROPIC_API_KEY`   | Get from https://console.anthropic.com (you must enable web search in the console too) |
| `TELEGRAM_BOT_TOKEN`  | `86xxxxxxx:AAxxxxxxxxxxxxxxxxx` |
| `TELEGRAM_CHAT_ID`    | `74xxxxxxxxxxx` |

### 3. Enable web search in Anthropic Console
The Anthropic admin must turn on web search for your org: Console → Settings → enable web_search tool.

### 4. Test locally first (optional)
```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
export TELEGRAM_BOT_TOKEN=...
export TELEGRAM_CHAT_ID=74xxxxxxxx
python scripts/run_intel.py
python scripts/send_telegram.py
```

### 5. Trigger manually first time
GitHub → Actions tab → "Joyun Daily Intelligence" → Run workflow.
After it succeeds once, the daily cron takes over.

## Cost
Per daily run with `claude-opus-4-7` + 10-15 web searches: roughly $0.50-1.50/day → **~$15-45/month**.
Switch the `MODEL` constant in `scripts/run_intel.py` to `claude-sonnet-4-6` to cut that to ~$5-15/month.

GitHub Actions is free (well within the 2,000 min/month free tier).

## Monthly reset
Per spec, you keep daily CSVs and reports forever, just overwrite `dashboard.html`. The repo serves as the archive — every commit is timestamped and reversible. To do the monthly reset:
```bash
mkdir -p archives/$(date +%Y-%m)
mv data/*.csv data/*.md archives/$(date +%Y-%m)/
git commit -am "Monthly archive"
```

## Files

```
joyun_intel/
├── scripts/
│   ├── run_intel.py          # Claude API research → CSV + report + dashboard
│   └── send_telegram.py      # Direct Bot API delivery
├── data/                     # Daily CSVs + reports + findings JSON
├── dashboard.html            # Latest dashboard (overwritten daily)
├── dashboard-template.html   # Reusable template
├── DASHBOARD_STYLE.md        # Locked visual style
├── CSV_STRUCTURE.md          # Locked CSV format
├── RESEARCH_SCOPE.md         # Locked research coverage
├── requirements.txt
└── .github/workflows/daily.yml
```
