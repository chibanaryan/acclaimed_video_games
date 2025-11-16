## Setup Local Development Environment

### Install Dependencies

* Python 3 (https://www.python.org/downloads/)
* Git   (https://git-scm.com/downloads/win)
* Heroku CLI    (https://devcenter.heroku.com/articles/heroku-cli)
* Node (https://nodejs.org/en/download)

### Setup Git Repository

Clone Git repo locally

    git clone git@bitbucket.org:sean2000/acclaimedgames.git

Login with Heroku CLI (should open a browser to authenticate)

    heroku login

Add Heroku remote (first time only)

    heroku git:remote -a acclaimedgames

### Web backend

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

### Web frontend

Install JavaScript dependencies (first time only)

    cd frontend
    npm install

Run Vue.js development server

    npm run dev

## Deploy New Version of Website

Firstly build the frontend JavaScript app

    cd frontend
    npm run build

Copy static files

    python manage.py collectstatic

Add the `dist` folder to the repo

    git add dist

To deploy to Heroku, push your local Git repo to the Heroku remote

    git commit -av -m "Some changes"
    git push heroku master

## Pre-commit Hooks

This repo uses [pre-commit](https://pre-commit.com/) to ensure the Django test
suite (`games/tests.py`) runs before every commit.

1. Install the tool (usually once per machine):

        pip install pre-commit

2. From the project root, enable the hooks:

        pre-commit install

With that in place, `scripts/run_tests.sh` executes automatically and blocks a
commit if the tests fail. Make sure your virtualenv is set up and dependencies
installed before running `pre-commit install`.

## Import New Data

1. Browse to `/import/`
1. Log in
2. Click on  "Delete existing data"
3. Under "Type" select "Platforms"
4. Click on "Upload a file..."
5. Select the text file containing platforms (PlatformDB.txt)
6. Click on "Submit"
6. Repeat for "Source lists" (SourceLists.txt), "Games" (Top1000.txt) and "Game positions" (GamePositions.txt)

Run the `get_igdb` command to import the data from IGDB (this will take some time to complete)

    python manage.py get_igdb

To run it on the remote Heroku server

    heroku run python manage.py get_igdb
