## Project Overview

Acclaimed Games is a video game ranking and aggregation website built with:
- **Django** - Backend framework with server-side rendering
- **HTMX** - Dynamic interactions without full page reloads
- **Alpine.js** - Client-side reactivity for UI components
- **Tailwind CSS v4** - Utility-first CSS framework
- **DaisyUI v5** - Component library for Tailwind

For detailed documentation, see [CLAUDE.md](CLAUDE.md).

## Setup Local Development Environment

### Prerequisites

- Python 3
- Node.js (for Tailwind CSS)
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

# Install Tailwind CSS dependencies
python3 manage.py tailwind install
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

**Note:** The Tailwind CSS watcher (`python3 manage.py tailwind start`) is only needed if you're actively editing styles. The compiled CSS is committed to git, so for most dev work you just need the Django server.

## Deploy to Production

```bash
python3 manage.py tailwind build
python3 manage.py collectstatic --noinput
git add -A
git commit -m "Your commit message"
git push origin main
git push heroku main
```

## CSS Workflow (Tailwind CSS)

The site uses django-tailwind with Tailwind CSS v4 and DaisyUI v5.

**Development:**
- Run `python3 manage.py tailwind start` to watch for changes
- Edit styles in `theme/static_src/src/styles.css`
- CSS automatically rebuilds on save

**Key Files:**
- `theme/static_src/src/styles.css` - Main Tailwind source with custom components
- `theme/static/css/dist/styles.css` - Compiled output (auto-generated)
- `games/static/games/css/mdi-subset.css` - Material Design Icons subset

**Theme Configuration:**
Themes are configured in `styles.css`:
```css
@plugin "daisyui" {
  themes: forest --default, night, sunset, nord, lofi;
}
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
- **Delete All Data** - Destructive maintenance reset for ranking data
- **Fetch IGDB Data** - Pull cover art, descriptions, and genres

### Batch Import

Upload tab-separated files in order:
1. **PlatformDB.txt** - `CODE<tab>Name`
2. **SourceLists.txt** - `Publisher<tab>Year<tab>Type<tab>Name<tab>URL`
3. **Games file (for example `Top1400.txt`)** - `Rank<tab>Name<tab>Year<tab>Platforms<tab>IGDB_ID<tab>Wikidata_ID`
4. **GamePositions.txt** - `ListID:Position<tab>ListID:Position...`

Regular batch import replaces the existing ranking dataset in place. You do not need to run the delete action first.

### IGDB Import on Heroku

```bash
heroku run python3 manage.py get_igdb
```
