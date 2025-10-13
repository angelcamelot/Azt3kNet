# Local infrastructure

This directory contains Docker resources that make it easy to spin up
the local dependencies required by Azt3kNet:

- **Postgres 15** for the primary persistence layer.
- **Redis 7** for background job queues.
- **Ollama** for local LLM inference with reproducible prompts.

## Quick start

1. Copy the environment defaults:

   ```bash
   cp infra/docker/.env.example infra/docker/.env
   ```

2. Launch the services:

   ```bash
   docker compose --env-file infra/docker/.env -f infra/docker/docker-compose.yml up -d
   ```

3. Stop the stack when you are done:

   ```bash
   docker compose --env-file infra/docker/.env -f infra/docker/docker-compose.yml down
   ```

The volumes declared in `docker-compose.yml` keep your Postgres data and
Ollama models between restarts.
