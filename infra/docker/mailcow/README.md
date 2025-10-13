# Mailcow deployment helper

This directory contains helper assets to embed the official
[mailcow/mailcow-dockerized](https://github.com/mailcow/mailcow-dockerized)
project into the Azt3kNet stack.

## Usage

1. Export the required environment variables (`DESEC_DOMAIN`, `AZT3KNET_DOMAIN`,
   `MAILCOW_API_KEY`, etc.) or populate a `.env` file.
2. Run `./infra/docker/mailcow/bootstrap.sh`. The script clones the upstream
   repository (if needed), runs `generate_config.sh` with the correct hostname
   (`mail.<domain>`) and writes a wrapper compose file.
3. Start Mailcow with:

   ```bash
   docker compose -f infra/docker/mailcow/docker-compose.mailcow.yml up -d
   ```

4. Obtain the initial API key from the Mailcow UI and inject it into the `.env`
   file so that the application can manage mailboxes.

The wrapper compose file relies on Docker Compose v2.20 or newer to support the
`include` directive. Alternatively, run the upstream compose file directly:

```bash
(cd infra/docker/mailcow/mailcow-dockerized && docker compose up -d)
```

## Volumes and backups

Mailcow stores data under the `infra/docker/mailcow/mailcow-dockerized/data`
folder. Back it up regularly together with the `.env` file to keep certificates,
mailboxes and Redis queues safe.

