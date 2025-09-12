# CheckPoint1
 - project description
	 A simple 2-tier retail prototype:
	 - Tier 1: minimal web UI (Flask) for listing products, cart, and checkout.
	 - Tier 2: SQLite database for persistent storage (Product, Sale, SaleItem, Payment).
	 Focus: clean structure, persistence abstraction (DAO), testing, and docs.

 - setup/run/test instructions
	 Prerequisites: Python 3.10+ (venv recommended)

	 Create venv and install deps:
	 ```bash
	 python -m venv .venv
	 source .venv/bin/activate
	 pip install -r requirements.txt
	 ```

	 Initialize the database (idempotent):
	 ```bash
	 python -m src.main
	 ```

		DEV-ONLY seed helper (temporary until Partner A ships user/product schema & seeds):
		```bash
		python -m src.dev_seed
		```
		Notes:
	 - This helper creates minimal user/product tables and demo rows so the UI works.
	 - Partner A will replace this with official schema and seed; this script is safe to delete then.

		Run the web UI (Flask):
	 ```bash
	 python -m src.app
	 ```
	 Open http://127.0.0.1:5000 and try adding to cart and checkout.

	 Run tests (pytest):
	 ```bash
	 pytest -q
	 ```

		Optional demo (scripted, no UI):
		```bash
		python -m src.demo_flow
		```

 - database setup instructions
	 Schema lives in `db/init.sql`. On app start (`python -m src.main`) it is applied to `app.sqlite` by default.
	 Environment variables:
	 - `APP_DB_PATH`: path to the SQLite file (default: `<repo>/app.sqlite`).
	 - `APP_SECRET_KEY`: Flask session secret (dev default provided).
	 - `APP_DEMO_USER_ID`: User ID used by checkout demo (default: 1).

	 Core tables (required): Product (A), Sale (B), SaleItem (B), Payment (B).
	 Persisted data remains across restarts because we use a file-backed SQLite DB.

 - team members’ names
	Pragya Chapagain
	Yanlin Wu
