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

		
		```bash
		python -m src.seed
		```
	

		Run the web UI (Flask):
	 ```bash
	 python -m src.app
	 ```
	 Open http://127.0.0.1:5000 and try adding to cart and checkout.

	 Run tests (pytest):
	# CheckPoint1

	Simple two-tier retail prototype.
	- UI: Flask app for products, cart, login/register, and checkout.
	- DB: SQLite file (app.sqlite by default) with schema for user/product (Partner A) and sale/sale_item/payment (Partner B).
	- Focus: clean structure, DAO seam, atomic checkout, and tests.

	## Quick start

	Prerequisites: Python 3.10+ (venv recommended)

	1) Setup
	```bash
	python -m venv .venv
	source .venv/bin/activate
	pip install -r requirements.txt
	```

	2) Initialize DB (idempotent)
	```bash
	python -m src.main
	```

	3) Seed demo data (users + products)
	```bash
	python -m src.seed
	```

	4) Run the web UI
	```bash
	python -m src.app
	```
	Open http://127.0.0.1:5000. Register or login, view products, search by name or add by Product ID/quantity, and checkout.

	Login with seeded users (from `src/seed.py`):
	- Username: john / Password: password123
	- Username: jane / Password: password123
	- Username: alice / Password: password123

	## Tests

	Run all tests:
	```bash
	pytest -q
	```
	Test suites:
	- tests/unit_test.py – end-to-end checkout (success, decline, concurrency).
	- tests/test_product_repo.py – Partner A’s product repo unit tests.

	## Project layout (key files)

	- db/init.sql – complete schema: user/product (A) + sale/sale_item/payment (B).
	- src/app.py – Flask app, routes, and wiring of repositories and payment.
	- src/dao.py – DAO helpers (get_connection, transaction), SalesRepo, and ProductRepo interface.
	- src/product_repo.py – AProductRepo: Partner A implementation of ProductRepo.
	- src/payment.py – mock payment processor (use method DECLINE_TEST to simulate declines).
	- src/main.py – init_db() applies db/init.sql to the configured SQLite file.
	- src/seed.py – seeds demo users (hashed passwords) and products.
	- templates/ – HTML templates for login/register/products/cart/receipt.
	- tests/ – pytest suites.

	## Environment variables

	- APP_DB_PATH – path to the SQLite file (default: <repo>/app.sqlite).
	- APP_SECRET_KEY – Flask session secret (dev default provided).
	- PORT – port for the Flask dev server (default 5000).

	DB path alignment:
	- Run `python -m src.main` before `python -m src.seed` so the DB file exists.
	- Ensure the seed writes to the same DB the app uses. By default both use `<repo>/app.sqlite`.
	- If you set `APP_DB_PATH` for the app, run seed against that same file (current seed uses the default path).

	## Design notes

	- Product access uses a repository seam:
		- dao.ProductRepo defines the contract (base/interface). Do not remove it.
		- src/product_repo.py provides AProductRepo(conn), passed into SalesRepo for real lookups.
	- Checkout is atomic:
		- BEGIN IMMEDIATE transaction; inserts sale, items, payment, and decrements stock.
		- Payment is mocked; method == "DECLINE_TEST" returns a decline.
	- Tests create their own temporary DBs and do not rely on app.sqlite.

	## Optional utilities

	- CLI demo: `python -m src.demo_flow` (scripted success/decline run). Useful for quick smoke-tests; optional.
	- Legacy seed: `src/dev_seed.py` was a DEV-ONLY scaffold. With src/seed.py in place, it’s no longer required.

	## Troubleshooting

	- “unrecognized token: #” while applying SQL – SQLite uses `--` for comments; ensure db/init.sql has `--` comments only.
	- Products page empty – run `python -m src.seed` after `python -m src.main` and ensure APP_DB_PATH points to the same file for app and seed.
	- Can’t login – use the seeded accounts (john/jane/alice with password123), or register a new user.

	### Password hashing compatibility

	Demo and newly registered users use PBKDF2 (pbkdf2:sha256) for maximum compatibility across Python/OpenSSL builds. Always run inside this project's virtual environment (.venv). If you previously seeded users with a different hash (e.g., scrypt) and see “ValueError: unsupported hash type scrypt:32768:8:1” on login, re-run:

	```bash
	APP_DB_PATH=$(pwd)/app.sqlite \
		.venv/bin/python -m src.main && \
	APP_DB_PATH=$(pwd)/app.sqlite \
		.venv/bin/python -m src.seed
	```

	This will update demo user hashes to PBKDF2.

	## Team

	- Pragya Chapagain
	- Yanlin Wu
