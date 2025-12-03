# Quote Curation Tools

This directory contains tools and documentation for curating video game quotes.

## Files

### Documentation
- **LLM_QUOTES_README.md** - Comprehensive guide to the LLM-powered quote service
- **LLM_QUOTE_CURATION_PROMPT.md** - Prompt template for manual LLM quote curation (for use with ChatGPT, Claude web, etc.)

### Scripts
- **test_llm_quotes.py** - Test script for the LLM quote service (requires Anthropic API key)

### Data Exports
- **wikiquote_100_test.csv** - Test results from scraping 100 games from Wikiquote
- **wiki_quotes_*.csv** - Various quote export snapshots

## Quick Start

### Testing Wikiquote Scraper
```bash
# Test single game
python3 manage.py get_quotes --game "Portal"

# Batch process and export to CSV
python3 manage.py get_quotes --limit 100 --output quotes_export.csv

# Save to database
python3 manage.py get_quotes --limit 100 --save
```

### Testing LLM Quote Service
```bash
# Requires: export ANTHROPIC_API_KEY="your-key"
python3 test_llm_quotes.py "Half-Life 2"
```

## Services

The project includes two quote services:

1. **Wikiquote Scraper** (`games/services/quote_service.py`)
   - Scrapes quotes from Wikiquote
   - Free, no API required
   - ~61% coverage for top 100 games

2. **LLM Quote Service** (`games/services/llm_quote_service.py`)
   - Uses Claude API to find and curate quotes
   - Can clean/improve Wikiquote results
   - Falls back to web search for missing games
   - Requires Anthropic API key
   - ~$0.004 per game

## Management Commands

See `python3 manage.py get_quotes --help` for full options:
- `--game NAME` - Process single game
- `--slug SLUG` - Process by slug
- `--limit N` - Process N games
- `--save` - Save to database
- `--output FILE.csv` - Export to CSV
- `--skip-existing` - Skip games with quotes
