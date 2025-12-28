---
name: refresh-metadata
description: Refresh all metadata from IGDB and Wikipedia. Use for weekly maintenance or full data refresh.
---

# Weekly Metadata Refresh

Combines `get_igdb --force` and `fetch_wikipedia_metadata --force --save` into one unified operation, designed for weekly scheduled execution.

## Usage

```bash
# Full refresh (weekly maintenance) - updates all games
python3 manage.py refresh_all_metadata

# IGDB only
python3 manage.py refresh_all_metadata --igdb-only

# Wikipedia only
python3 manage.py refresh_all_metadata --wikipedia-only

# Test with limited games
python3 manage.py refresh_all_metadata --limit 100

# Dry-run (preview without database changes)
python3 manage.py refresh_all_metadata --dry-run

# With IGDB Pro tier
python3 manage.py refresh_all_metadata --pro
```

## Command Options

| Option | Description |
|--------|-------------|
| `--igdb-only` | Only refresh IGDB data (skip Wikipedia) |
| `--wikipedia-only` | Only refresh Wikipedia data (skip IGDB) |
| `--limit N` | Process only first N games (for testing) |
| `--dry-run` | Preview operations without database changes |
| `--concurrency N` | Override IGDB concurrency (default: 8) |
| `--pro` | Use IGDB Pro tier |

## Performance

| Mode | Duration |
|------|----------|
| Full refresh (3000+ games, authenticated) | ~40 minutes |
| IGDB only (free tier) | ~30 seconds |
| IGDB only (pro tier) | ~3 seconds |
| Wikipedia only (authenticated) | ~38 minutes |

## Heroku Scheduler Setup

```bash
# Add Heroku Scheduler add-on
heroku addons:create scheduler:standard
```

Configure in Heroku Dashboard (https://dashboard.heroku.com):
- **Command:** `python3 manage.py refresh_all_metadata`
- **Schedule:** Weekly (Sunday 2:00 AM UTC recommended)
- **Dyno:** Performance-M (recommended for 40-minute job)
- **Duration:** ~40 minutes

## Required Environment Variables

| Variable | Description |
|----------|-------------|
| `IGDB_CLIENT_ID` | IGDB API client ID |
| `IGDB_CLIENT_SECRET` | IGDB API secret |
| `WIKIDATA_ACCESS_TOKEN` | Highly recommended (2.5x faster Wikipedia processing) |
| `IGDB_USE_PRO_TIER` | Optional (enables Pro tier, 750x faster IGDB) |
