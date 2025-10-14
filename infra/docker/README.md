# Local infrastructure

This directory contains Docker resources that make it easy to spin up
the local dependencies required by Azt3kNet:

- **Postgres 16** for the primary persistence layer with the `pgvector` extension.
- **Redis 7** for background job queues.
- **Ollama** for local LLM inference with reproducible prompts.
- **MinIO** exposing an S3-compatible API for blob storage (ports `9000/9001`).

## Quick start

1. Copy the environment defaults (or run `./scripts/bootstrap_env.sh`):

   ```bash
   cp infra/docker/.env.example infra/docker/.env
   ```

2. Launch the services that back the application:

   ```bash
   docker compose --env-file infra/docker/.env -f infra/docker/docker-compose.yml up -d
   ```

3. (Optional) Once MinIO reports healthy, create any required buckets:

   ```bash
   poetry run python scripts/setup_minio.py
   ```

   The helper relies on the same environment variables defined in `.env` and
   only creates buckets that are missing. Install the
   [`minio`](https://pypi.org/project/minio/) Python client in your
   environment before running the script if it is not already available.

4. Stop the stack when you are done:

   ```bash
   docker compose --env-file infra/docker/.env -f infra/docker/docker-compose.yml down
   ```

The volumes declared in `docker-compose.yml` keep your Postgres data and
Ollama models between restarts. The new `minio-data` volume persists the S3
objects stored locally.

> **Tip:** The repository root now includes a `docker-compose.yml` that
> builds and runs the FastAPI surface together with these dependencies.
> Use `./scripts/dev_up.sh` to start the full stack in one command.

## Postgres extensions and TimescaleDB

- `infra/docker/postgres-init/00-enable-vector.sql` runs on first boot to
  execute `CREATE EXTENSION IF NOT EXISTS vector;` so the embeddings
  extension is always available.
- `infra/docker/postgres-init/01-enable-timescaledb.sh` runs when
  `POSTGRES_ENABLE_TIMESCALEDB=true` to execute
  `CREATE EXTENSION IF NOT EXISTS timescaledb;`. Combine it with the
  TimescaleDB image when you need hypertables or continuous aggregates.

To opt-in to TimescaleDB replace the image and enable the flag in
`infra/docker/.env` before starting the stack:

```env
POSTGRES_IMAGE=timescale/timescaledb-ha:pg16
POSTGRES_ENABLE_TIMESCALEDB=true
TIMESCALEDB_MAX_MEMORY=1GB
```

The `infra/docker/postgres-init/02-configure-memory.sh` helper appends the
requested `shared_buffers` and optional `timescaledb.max_memory` settings
to `postgresql.conf` during initialisation. Adjust the defaults in
`infra/docker/.env` to match your workstation resources.

## MinIO configuration

The compose file exposes the MinIO API on `localhost:9000` and the admin
console on `localhost:9001`. The defaults shipped in `.env.example` align
with the application configuration:

```env
MINIO_ROOT_USER=azt3knet
MINIO_ROOT_PASSWORD=azt3knet123
MINIO_PORT=9000
MINIO_CONSOLE_PORT=9001
MINIO_ENDPOINT_INTERNAL=http://minio:9000
```

Application services consume the S3 endpoint and credentials through the
root `.env` file (`MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`,
`MINIO_SECRET_KEY`, `AZT3KNET_BLOB_BUCKET`, etc.). Copy the templates with
`./scripts/bootstrap_env.sh` and adjust as needed before bootstrapping
MinIO buckets.

## Migration note

Upgrading from Postgres 15 to Postgres 16 changes the on-disk format. Stop
containers, back up your data, and recreate the `postgres-data` volume if
you previously ran the old image. Developers using `scripts/dev_up.sh`
should run `docker compose down --volumes` once to avoid version conflicts.
