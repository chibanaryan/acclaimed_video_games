## Project Overview

Acclaimed Games is a video game ranking and aggregation website built with:
- **Django** - Backend framework with server-side rendering
- **HTMX** - Dynamic interactions without full page reloads
- **Alpine.js** - Client-side reactivity for UI components
- **Bulma CSS** - Styling with Bulmaswatch Cyborg theme

For detailed documentation, see [CLAUDE.md](CLAUDE.md).

## Setup Local Development Environment

### Install Dependencies

* Python 3 (https://www.python.org/downloads/)
* Git   (https://git-scm.com/downloads/win)
* Heroku CLI    (https://devcenter.heroku.com/articles/heroku-cli)

### Setup Git Repository

Clone Git repo locally

    git clone git@bitbucket.org:sean2000/acclaimedgames.git

Login with Heroku CLI (should open a browser to authenticate)

    heroku login

Add Heroku remote (first time only)

    heroku git:remote -a acclaimedgames

### Backend Setup

Create a Python virtual environment (first time only)

    py -m venv venv

Activate the virtual environment

    source venv\Scripts\activate

Install Python packages (first time only)

    pip install -r requirements.txt

Create the sqlite database (first time only)

    python manage.py migrate

Create a local user account (first time only)

    python manage.py createsuperuser

Run Django development server

    python manage.py runserver

## Deploy New Version of Website

Collect static files:

    python manage.py collectstatic --noinput

Commit your changes:

    git add -A
    git commit -m "Your commit message"

Push to GitHub:

    git push origin main

Deploy to Heroku:

    git push heroku main

## Pre-commit Hooks

This repo uses [pre-commit](https://pre-commit.com/) to ensure consistent
styling (via [Black](https://black.readthedocs.io/)) and that the Django test
suite (`games/tests.py`) runs before every commit.

1. Install the tool (usually once per machine):

    ```bash
    pip install pre-commit
    ```

2. From the project root, enable the hooks:

    ```bash
    pre-commit install
    ```

With that in place:

- Black runs automatically and formats Python code (commits will fail if files
  need reformatting).
- Flake8 runs immediately afterward to flag lint violations (imports, unused
  vars, long lines, etc.) so issues are caught before CI.
- `scripts/run_tests.sh` executes automatically and blocks a commit if the
  Django tests fail.
- Backend coverage is enforced (`coverage run --source=games manage.py test` with
  a fail-under threshold of 95%). You can run it manually via:

    ```bash
    source venv/bin/activate
    DATABASE_URL=sqlite:///db.sqlite3 CACHE_URL=locmemcache:// \
    CORS_ALLOWED_ORIGINS=http://localhost \
        COVERAGE_FILE=.coverage.backend \
        coverage run --source=games manage.py test games.tests
    coverage html  # view report at htmlcov/index.html
    ```

The HTML report lives under `htmlcov/index.html` (ignored by Git).

Make sure your virtualenv is set up and dependencies installed before running
`pre-commit install`.

## Import New Data

The import page at `/import/` provides a modern interface for managing game data:

### Quick Actions

**Load Test Data (Development only)**
- Click the "📦 Load Test Data (Dev)" button to quickly load bundled test files
- Only available when `DEBUG=True`
- Automatically imports platforms, source lists, games, and game positions

**Delete All Data**
- Click "🗑️ Delete All Data" to wipe the database
- Use this before importing a fresh dataset

**Fetch IGDB Data**
- Click "🔄 Fetch IGDB Data" to pull cover art, descriptions, and genres from IGDB
- Shows real-time progress with a visual progress bar
- Can also be run from command line: `python manage.py get_igdb`

### Batch Import

To import custom data files:

1. Navigate to `/import/` and log in
2. Upload all required files (they'll be processed in order):
   - **PlatformDB.txt** - Gaming platforms (tab-separated: `CODE<tab>Name`)
   - **SourceLists.txt** - Critic rankings (tab-separated: `Publisher<tab>Year<tab>Type<tab>Name<tab>URL`)
   - **Top1000.txt** - Games database (tab-separated: `Rank<tab>Name<tab>Year<tab>IGDB_ID<tab>Platforms`)
   - **GamePositions.txt** - Game positions in lists (tab-separated: `ListID:Position<tab>ListID:Position...`)
3. Check "Automatically fetch IGDB data after import" if desired
4. Click "📤 Import Files"
5. Monitor real-time progress for each file

The import page also displays database statistics showing counts for all data types and IGDB completion percentage.

### IGDB Import on Heroku

To run IGDB data fetch on production:

    heroku run python manage.py get_igdb
