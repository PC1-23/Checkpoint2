# CheckPoint1

## Project description

CheckPoint1 is a simple two-tier retail prototype built with Flask (web UI) and SQLite (persistence). Users can view products, add items to a cart, register/login, and checkout. Data is stored in a SQLite database and all checkout operations run atomically via a small DAO layer.

## Setup / Run / Test instructions

Prerequisites: Python 3.10+ (use a virtual environment)

1) Setup
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2) Run the app
```bash
# Make sure the database is initialized and seeded (see next section)
python -m src.app
```
Open http://127.0.0.1:5000 in your browser.

3) Run tests
```bash
pytest -q
```

## Database setup instructions

The app uses a SQLite file (default path: <repo>/app.sqlite).

1) Initialize schema (idempotent)
```bash
python -m src.main
```

2) Seed demo data (users + products)
```bash
python -m src.seed
```

Options
- You can override the DB location by setting APP_DB_PATH, e.g.:
	```bash
	APP_DB_PATH=$(pwd)/app.sqlite python -m src.main
	APP_DB_PATH=$(pwd)/app.sqlite python -m src.seed
	```
- Seeded users for quick login:
	- john / password123
	- jane / password123
	- alice / password123

## Team members

- Pragya Chapagain
- Yanlin Wu
