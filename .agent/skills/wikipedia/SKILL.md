---
name: wikipedia
description: Fetch Wikipedia metadata and genres for games. Use when asked to get Wikipedia data or genres.
---

# Wikipedia Metadata Fetch

Fetch Wikipedia page titles and genre data for games.

## Primary Command: fetch_wikipedia_metadata

This is the **recommended command** for fetching Wikipedia data. It combines two operations:
1. Looks up Wikipedia page titles using Wikidata IDs (fast) with fallback to OpenSearch API
2. Scrapes genre data from those Wikipedia pages (primary genre and all genres)

### Usage

```bash
# Fetch Wikipedia pages and genres for all games needing data (recommended)
python3 manage.py fetch_wikipedia_metadata --save --skip-existing

# Process all games (force refresh)
python3 manage.py fetch_wikipedia_metadata --save --force

# Process with limit
python3 manage.py fetch_wikipedia_metadata --save --limit 100

# Process single game (for testing)
python3 manage.py fetch_wikipedia_metadata --game "The Legend of Zelda" --save
```

### Options

| Option | Description |
|--------|-------------|
| `--save` | Save results to database |
| `--skip-existing` | Skip games that already have data |
| `--force` | Force refresh all games |
| `--limit N` | Process only first N games |
| `--game NAME` | Process single game by name |

### Results Storage

- `WikipediaGameData` records - stores page titles
- `WikipediaGenre` objects - stores genres

---

## Standalone Genre Command: get_wiki_genres

Use this command **only if you need genre data without page titles**.

### Usage

```bash
# Process all games (outputs to CSV)
python3 manage.py get_wiki_genres

# Process all games and save to database
python3 manage.py get_wiki_genres --save

# Process single game (for testing)
python3 manage.py get_wiki_genres --game "The Legend of Zelda"

# Process with limit
python3 manage.py get_wiki_genres --limit 100

# Skip games that already have Wikipedia genre data
python3 manage.py get_wiki_genres --skip-existing --save
```

### How It Works

Uses a cascade approach:
1. First queries Wikidata P136 (Genre) property
2. Falls back to scraping Wikipedia infobox if Wikidata fails

### Results Storage

- `Game.wikipedia_primary_genre` - primary genre field
- `Game.wikidata_id` - Wikidata entity ID

**Note:** Use `fetch_wikipedia_metadata` instead if you also need Wikipedia page titles.
