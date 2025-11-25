## Project Overview

Acclaimed Games is a video game ranking and aggregation website built with:
- **Django** - Backend framework with server-side rendering
- **HTMX** - Dynamic interactions without full page reloads
- **Alpine.js** - Client-side reactivity for UI components
- **Bulma CSS** - Styling with Bulmaswatch Cyborg theme

For detailed documentation, see [CLAUDE.md](CLAUDE.md).

## Setup Local Development Environment

### Prerequisites

- Python 3
- Git
- Heroku CLI

### Clone Repository

```bash
git clone https://github.com/chibanaryan/acclaimedgames.git
cd acclaimedgames
heroku login
heroku git:remote -a acclaimedgames
```

### Install Dependencies

```bash
python3 -m venv venv

# macOS/Linux:
source venv/bin/activate

# Windows:
venv\Scripts\activate

pip install -r requirements.txt
pre-commit install
```

### Get Data

**Option A: Sync from Production (Recommended)**

```bash
python3 manage.py sync_from_prod
python3 manage.py createsuperuser
```

**Option B: Start Fresh**

```bash
python3 manage.py migrate
python3 manage.py createsuperuser
```

Then import data via `/import/` (see [Import New Data](#import-new-data) below).

### Run Development Server

```bash
python3 manage.py runserver
```

## Deploy to Production

```bash
python3 manage.py collectstatic --noinput
git add -A
git commit -m "Your commit message"
git push origin main
git push heroku main
```

## Pre-commit Hooks

This repo uses [pre-commit](https://pre-commit.com/) to enforce code quality:

- **Black** - Auto-formats Python code
- **Flake8** - Lints for style violations
- **Tests** - Runs full test suite
- **Coverage** - Enforces 95% minimum coverage

Commits are blocked if any check fails. Run tests manually:

```bash
python3 manage.py test games.tests
```

## Import New Data

The `/import/` page is for adding **new source lists** to the database (not for initial setup - use `sync_from_prod` for that).

### Quick Actions

- **Load Test Data** - Load bundled test files (development only)
- **Delete All Data** - Wipe the database before fresh import
- **Fetch IGDB Data** - Pull cover art, descriptions, and genres

### Batch Import

Upload tab-separated files in order:
1. **PlatformDB.txt** - `CODE<tab>Name`
2. **SourceLists.txt** - `Publisher<tab>Year<tab>Type<tab>Name<tab>URL`
3. **Top1000.txt** - `Rank<tab>Name<tab>Year<tab>IGDB_ID<tab>Platforms`
4. **GamePositions.txt** - `ListID:Position<tab>ListID:Position...`

### IGDB Import on Heroku

```bash
heroku run python3 manage.py get_igdb
```
