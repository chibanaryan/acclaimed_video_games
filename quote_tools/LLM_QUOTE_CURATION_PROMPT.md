# Video Game Quote Curation Task

I need you to curate memorable character quotes from video games. For each game listed below, find 3-5 iconic quotes and return them in CSV format.

## Quote Selection Criteria (Priority Order)

1. **Iconic/famous quotes** that define the game or character
2. **Emotionally resonant** or dramatic moments
3. **Witty, quippy, or humorous** dialogue
4. Quotes that **capture the game's theme** or essence
5. **Character-defining moments**

## Requirements

- Each quote MUST be **under 200 characters**
- Each quote MUST have **attribution** (character name or "In-game dialogue")
- Prioritize **verified quotes** from the actual game (not made up)
- Clean up any grammar errors, typos, or formatting issues
- Remove reference markers like [1], [citation needed]
- **Reject**: Sound effects (AAAH!), incomplete sentences, reviewer commentary

## Output Format

Return data in CSV format with these columns:
```
Rank,Game Name,Source,Quote Count,Quotes JSON,Source URL,Error
```

**Quotes JSON format** (as a JSON array string):
```json
[
  {"text": "The actual quote", "attribution": "Character Name"},
  {"text": "Another quote", "attribution": "Character Name"}
]
```

## Example Row

```csv
5,Half-Life 2,Manual Curation,3,"[{""text"": ""Rise and shine, Mr. Freeman."", ""attribution"": ""G-Man""}, {""text"": ""The right man in the wrong place can make all the difference in the world."", ""attribution"": ""G-Man""}, {""text"": ""About that beer I owed ya!"", ""attribution"": ""Barney Calhoun""}]",Multiple sources,
```

## Games to Process (Top 20 Priority)

These games from the top 100 don't have quotes yet:

1. **Rank 5: Half-Life 2**
2. **Rank 16: Doom**
3. **Rank 19: The Elder Scrolls V: Skyrim**
4. **Rank 25: Metal Gear Solid**
5. **Rank 26: Halo: Combat Evolved**
6. **Rank 32: Castlevania: Symphony of the Night**
7. **Rank 34: GoldenEye 007**
8. **Rank 36: Half-Life**
9. **Rank 42: Metal Gear Solid 3: Snake Eater**
10. **Rank 43: StarCraft**
11. **Rank 45: Diablo II**
12. **Rank 46: Final Fantasy VI**
13. **Rank 47: Star Wars: Knights of the Old Republic**
14. **Rank 48: Super Mario Kart**
15. **Rank 50: Super Mario Odyssey**
16. **Rank 53: Super Mario Galaxy**
17. **Rank 57: Grand Theft Auto III**
18. **Rank 60: Overwatch**
19. **Rank 61: Grand Theft Auto IV**
20. **Rank 62: Tomb Raider**

## Task Instructions

1. **For each game above**, find 3-5 memorable quotes
2. **Verify** quotes are real (use your knowledge or search)
3. **Format** each game as a CSV row
4. **Return** all rows together so I can save to a file

## Start Here

Please process all 20 games above and return the complete CSV output. Make sure to:
- Use proper CSV escaping (double quotes inside JSON strings should be `""`)
- Keep quotes under 200 characters
- Provide character attribution for every quote
- Focus on the most iconic/memorable dialogue

Begin with the CSV header, then provide one row per game.
