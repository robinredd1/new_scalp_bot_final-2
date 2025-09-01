# News Scalp Bot (Finnhub-powered)

**This build hardcodes your Finnhub API key in `config.py` so it will run even if `.env` is missing.**

Finds U.S. stocks priced **$2–$20** that are:
- **Up ≥ 10%** today
- **Relative volume ≥ 5×** (vs. 10‑day avg, time-adjusted)
- **Fresh news catalyst** in the **last 120 minutes**

## Quick Start
```bash
pip install -r requirements.txt
python bot.py
```
If you use Replit: import the repo → Run.

## Security
Your key is inside `config.py`. If you push to **public GitHub**, rotate the key or switch to `.env`.