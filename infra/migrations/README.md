# Alembic migrations

Place Alembic environment files and migration scripts here. The
structure is compatible with the default Alembic layout generated via
`alembic init`:

- `alembic.ini` (placed at `infra/migrations/alembic.ini`)
- `env.py`
- `script.py.mako`
- `versions/` directory with revision files

Refer to the CLI command `poetry run alembic --config infra/migrations/alembic.ini revision --autogenerate -m "message"` to
create new migrations.
