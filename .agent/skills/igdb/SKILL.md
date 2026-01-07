---
name: igdb
description: Import game data from IGDB API. Use when asked to fetch, import, or refresh IGDB data.
---

# IGDB Data Import

Import game data from the IGDB (Internet Game Database) API.

## Basic Usage

```bash
# Default command uses maximum throughput (concurrency=8, tier-aware batching)
# Free tier: batch=50, Pro tier: batch=500
python3 manage.py get_igdb
```

## Command Options

| Option | Description |
|--------|-------------|
| `--concurrency N` | Number of concurrent requests (1-8, default: 4) |
| `--batch-games N` | Batch size for multi-query (0-500, default: 10) |
| `--delay SECONDS` | Additional delay between games (default: 0.0) |
| `--batch-size N` | Progress checkpoint interval (default: 50) |
| `--pro` | Use IGDB Pro tier (or set IGDB_USE_PRO_TIER=True in .env) |
| `--force` | Force refresh even if game already has IGDB data |
| `--game NAME` | Update specific game by name |
| `--slug SLUG` | Update specific game by slug |
| `--id ID` | Update specific game by database ID |

## Examples

```bash
# Conservative mode (slower but safer)
python3 manage.py get_igdb --concurrency 4 --batch-games 20

# Sequential mode (disable optimizations)
python3 manage.py get_igdb --concurrency 1 --batch-games 0

# Pro tier (requires subscription - 750x faster rate limit + 10x batch size)
python3 manage.py get_igdb --pro

# Force refresh a specific game
python3 manage.py get_igdb --game "The Legend of Zelda" --force
```

## Performance Metrics

| Mode | Speed |
|------|-------|
| Free tier defaults (batch=50, concurrency=8) | ~100 games/sec |
| Pro tier defaults (batch=500, concurrency=8) | ~1000+ games/sec |
| Default settings (concurrency=4, batch-games=10) | ~8-10 games/sec |
| Sequential mode (--concurrency 1 --batch-games 0) | ~2 games/sec |
| Aggressive settings (concurrency=6, batch-games=20) | ~15-20 games/sec |
| With Pro tier (--pro) | ~100-500 games/sec |

**Benchmark:** 1000 games: ~10 seconds (free) vs ~1 second (pro)

## Environment Variables

| Variable | Description |
|----------|-------------|
| `IGDB_CLIENT_ID` | IGDB API client ID (required) |
| `IGDB_CLIENT_SECRET` | IGDB API client secret (required) |
| `IGDB_USE_PRO_TIER` | Enable Pro tier (default: False) |

## What IGDB Provides

- Cover art images
- Game descriptions
- Developer information
- Genre classifications

## Programmatic Usage

```python
# Fetch and save IGDB data for a single game
game.get_igdb_data()
```
