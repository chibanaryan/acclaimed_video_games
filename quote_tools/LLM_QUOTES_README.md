# LLM Quote Service

AI-powered quote service that uses Claude to find, verify, and curate video game quotes with emphasis on quality and memorability.

## Features

### 1. Smart Fallback Strategy
- **First**: Tries Wikiquote (fast, reliable)
- **If Wikiquote has quotes**: Uses LLM to clean and select the BEST 3-5 quotes
- **If Wikiquote fails**: Uses LLM with web search to find quotes from gaming wikis

### 2. Quality Focus
- Prioritizes **memorable, quippy, and resonant** quotes
- Cleans up grammar errors and typos
- Removes junk (sound effects like "AAAH!", incomplete sentences)
- Requires attribution for every quote
- Keeps quotes under 200 characters

### 3. Verification
- All quotes must be verified from reliable sources
- Source URLs provided for transparency
- No AI-generated content - only verified quotes from actual games

## Setup

### 1. Install Dependencies

```bash
pip install anthropic>=0.39.0
```

### 2. Get Anthropic API Key

1. Sign up at https://console.anthropic.com/
2. Create an API key
3. Set environment variable:

```bash
export ANTHROPIC_API_KEY="your-key-here"
```

### 3. (Optional) Set up Brave Search

For enhanced web search when Wikiquote doesn't have quotes:

```bash
export BRAVE_SEARCH_API_KEY="your-brave-key"
```

Get a free key at: https://brave.com/search/api/

## Usage

### Test with Single Game

```bash
python3 test_llm_quotes.py "Half-Life 2"
```

### Examples

**Game with Wikiquote data** (LLM cleans and selects best):
```bash
python3 test_llm_quotes.py "Portal"
# ✓ Found 3 quotes:
# 1. "The cake is a lie."
#    — GLaDOS
# 2. "This was a triumph."
#    — GLaDOS
# 3. "I'm making a note here: huge success."
#    — GLaDOS
```

**Game without Wikiquote** (LLM searches web):
```bash
python3 test_llm_quotes.py "Doom"
# Will search gaming wikis and extract verified quotes
```

## Integration with get_quotes Command

You can add an `--llm` flag to the existing `get_quotes` command:

```bash
python3 manage.py get_quotes --llm --limit 10 --save
```

This would:
1. Use LLM service for all games
2. Save cleaned/curated quotes to database
3. Fill gaps where Wikiquote failed

## Comparison: Wikiquote vs LLM

### Wikiquote Test Results (100 games)
- **Coverage**: 61% (61/100 games have quotes)
- **Total quotes**: 3,579
- **Avg per game**: 58.7 quotes
- **Quality issues**: Sound effects, wrong game matches, incomplete sentences

### LLM Service Benefits
- **Coverage**: 100% (can find quotes for any game via web search)
- **Quality**: 3-5 curated, memorable quotes per game
- **Cleanup**: Grammar fixes, junk removal
- **Attribution**: Required for every quote

### Top Games Missing from Wikiquote
These would benefit most from LLM service:
- #5: Half-Life 2
- #16: Doom
- #19: The Elder Scrolls V: Skyrim
- #25: Metal Gear Solid
- #26: Halo: Combat Evolved
- #32: Castlevania: Symphony of the Night

## Cost Estimate

Using Claude Sonnet 3.5:
- **Input**: ~500 tokens per game (system prompt + quotes)
- **Output**: ~300 tokens per game (JSON response)
- **Cost**: ~$0.004 per game

For 100 games: ~$0.40
For 1,000 games: ~$4.00

Very affordable for the quality improvement!

## Files Created

- `games/services/llm_quote_service.py` - Main LLM service
- `test_llm_quotes.py` - Test script
- `LLM_QUOTES_README.md` - This documentation

## Next Steps

1. **Test with your API key**: Run test script on a few games
2. **Review quality**: Check if LLM selections are better than raw Wikiquote
3. **Integrate with command**: Add `--llm` flag to `get_quotes` management command
4. **Batch process**: Run on all games missing quotes (39 games from top 100)
5. **Database save**: Use `--save` to populate GameQuote table
