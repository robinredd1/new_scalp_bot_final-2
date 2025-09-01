import os

# Your key is hardcoded below; env var can override if set.
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY") or "d2f3fq9r01qj3egr0apgd2f3fq9r01qj3egr0aq0"

# Scan settings
PRICE_MIN = 2.0
PRICE_MAX = 20.0
MIN_PCT_CHANGE = 10.0        # >= 10%
MIN_REL_VOL = 5.0            # >= 5x
NEWS_LOOKBACK_MIN = 120      # last 120 minutes news catalyst window

# Performance / rate-limits (tune for your plan)
SCAN_BATCH = 150             # symbols per batch
SLEEP_SECONDS = 2.0          # delay between batches

# Pre/Post behavior
PREPOST_PROGRESS = 0.20      # used in rVol denominator outside regular hours
REGULAR_SESSION_START_ET = "09:30"
REGULAR_SESSION_END_ET   = "16:00"

# Optional: a quick pre-filter watchlist (empty = all US symbols)
WATCHLIST = []  # e.g., ["NBY","AZTR","DSSD"]