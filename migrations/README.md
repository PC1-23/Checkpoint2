Migration process (local / dev)
------------------------------

This project uses simple SQL migration files under `migrations/` for
local and staging use. Each migration is an SQL script that will be run in
lexicographical order by `scripts/run_migrations.py`.

How to run migrations locally

1. Ensure you have a working copy of the DB. By default the runner uses
   `app.sqlite` at the repo root. You can override with:

   ```bash
   export APP_DB_PATH=/path/to/your/app.sqlite
   python scripts/run_migrations.py
   ```

2. Add migration files as `migrations/000N_description.sql`.

Notes
- For production use, switch to a real migration tool (Alembic, Flyway,
  etc.). This simple runner is intended to make local development and
  CI testing of migrations straightforward.
