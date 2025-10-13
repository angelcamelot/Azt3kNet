# Mail automation architecture

This document describes how Azt3kNet provisions real mailboxes for every agent by
combining **Mailcow** (self-hosted mail platform) with **deSEC** (DNSSEC-enabled
DynDNS provider).

## Overview

```
+-----------------+          +----------------------+          +------------------+
| Azt3kNet Core   |  HTTPS   | Mailcow API          |  HTTPS   | deSEC API        |
|  - agent model  +--------->+  /api/v1/add/mailbox +--------->+  /domains/...    |
|  - orchestrator |          |  /get/dkim/<domain>  |          |  DynDNS          |
+-----------------+          +----------------------+          +------------------+
         |                            |                                  |
         | SMTP/IMAP                  | generates DKIM                   |
         v                            v                                  v
   Agent mailbox <------------------- Mailcow stack <---------------- DNS records
```

* Mailcow runs inside the Docker stack and exposes Postfix, Dovecot, Rspamd and
  ACME automation. An API key allows Azt3kNet to manage domains, mailboxes and
  app passwords.
* deSEC hosts the public DNS zone and offers a DynDNS endpoint to keep the
  `dedyn.io` hostname pointing to the current residential IP address.
* Azt3kNet modules orchestrate both systems to provide a first-class `@domain`
  inbox per agent/bot.

## Configuration

All secrets and endpoints live in the shared `.env` file. See
[`.env.example`](../.env.example) for the full list of variables. The critical
values are:

| Variable | Purpose |
| --- | --- |
| `DESEC_DOMAIN` | Base dedyn.io domain managed in deSEC |
| `DESEC_TOKEN` | API token with RRset and DynDNS scopes |
| `MAILCOW_API_KEY` | Mailcow API key for the provisioning account |
| `AZT3KNET_AGENT_MAIL_PREFIX` | Prefix used when generating agent mailboxes |

## Runtime components

### Mail provisioning service

The `MailcowProvisioner` class located in `azt3knet.services.mailcow_provisioner`
wraps the REST API. It can:

* ensure that the target domain exists
* create a mailbox (`agent_<id>@domain`) with quota, rate limit and human-friendly
  display name
* generate and persist Mailcow app-passwords for SMTP/IMAP clients
* optionally configure an outbound SMTP relay such as Sendgrid when direct port
  25 access is unavailable

### DNS automation

`DeSECDNSManager` automates RRset management and DynDNS updates via the deSEC
API. It exposes helpers to:

* bulk upsert MX, SPF, DKIM and DMARC records using Mailcow-generated keys
* patch the `mail.<domain>` A record with the currently detected public IP
* call `https://update.dedyn.io` with token authentication to refresh the
  dynamic DNS assignment every 24 hours (configurable)

The script `scripts/dns_bootstrap.py` ties both services together: it fetches the
latest DKIM key from Mailcow, discovers the public IP, updates DNS RRsets and
triggers a DynDNS refresh. This script is designed to run at container startup
(via Docker entrypoint or cron).

### Mail access helper

`MailService` is a lightweight SMTP/IMAP wrapper that converts the mailbox
credentials into `email.message.EmailMessage` instances for sending and polling
messages. It supports catch-all inbox processing and can be extended to integrate
with the existing eventing system.

## Docker integration

Mailcow bootstrap assets live under `infra/docker/mailcow`. During installation:

1. Run `./infra/docker/mailcow/bootstrap.sh` to clone the official
   `mailcow/mailcow-dockerized` repository and generate configuration files that
   point to `mail.<domain>`.
2. Start the stack with `docker compose -f infra/docker/mailcow/docker-compose.mailcow.yml up -d`
   (the helper script writes this file to wrap the upstream compose project).
3. The `.env` variables expose Mailcow to the rest of the services.

The main `docker-compose.yml` keeps Azt3kNet services decoupled; they reach
Mailcow via the internal Docker network or public hostname depending on the
deployment scenario.

## Installation guide

### Prerequisites

- A public domain delegated to deSEC (for example `your-prefix.dedyn.io`).
- Docker and Docker Compose installed on the host that will run Mailcow.
- Ports 25/tcp, 80/tcp, 443/tcp, 587/tcp, and 993/tcp reachable from the
  internet (forwarded if running behind a router).
- Python 3.11+ available locally to execute the helper scripts.

### Install Mailcow

1. Copy `.env.example` to `.env` and set the Mailcow variables:

   ```bash
   cp .env.example .env
   ```

   Provide at least `MAILCOW_API`, `MAILCOW_API_KEY`, `MAILCOW_SMTP_HOST`,
   `MAILCOW_IMAP_HOST`, `MAILCOW_SMTP_PORT`, and `MAILCOW_IMAP_PORT`.

2. Bootstrap the Mailcow project from the repository root:

   ```bash
   ./infra/docker/mailcow/bootstrap.sh
   ```

   This clones the upstream `mailcow/mailcow-dockerized` repository inside
   `infra/docker/mailcow/mailcow-dockerized` and generates configuration files
   pointing to `mail.<your-domain>`.

3. Start the Mailcow stack:

   ```bash
   docker compose -f infra/docker/mailcow/docker-compose.mailcow.yml up -d
   ```

   Wait until all containers report a `healthy` status (`docker compose ps`).

4. Access the Mailcow UI at `https://mail.<your-domain>` and create the admin
   account. Generate an API key with domain and mailbox permissions and copy it
   to the `.env` file (`MAILCOW_API_KEY`).

5. (Optional) Configure an outbound SMTP relay under **Configuration → Mail
   Setup → Outgoing** if your ISP blocks port 25.

### Configure deSEC DynDNS

1. Create an account at [https://desec.io](https://desec.io) and add your
   hostname (for example `your-prefix.dedyn.io`). Enable DynDNS for the domain.

2. Generate an API token with RRset read/write permissions and DynDNS access.
   Store it in `.env` as `DESEC_TOKEN`.

3. Set `DESEC_DOMAIN` to the managed hostname (for example `your-prefix.dedyn.io`).
   Optionally override `DESEC_DYNDNS_UPDATE_URL` if you use a custom endpoint.

4. Run the initial bootstrap once the Mailcow stack is ready:

   ```bash
   poetry run python infra/dns_bootstrap.py
   ```

   The script will publish MX/SPF/DKIM/DMARC records based on the Mailcow
   configuration and synchronize the public IP address.

5. Schedule the dynamic updater (inside the container or host) to refresh the
   IP mapping:

   ```bash
   poetry run python infra/dyn_updater.py
   ```

   When running inside Docker, add a cron job or systemd timer that executes the
   command every few hours (the exact interval is controlled by
   `DESEC_UPDATE_INTERVAL_HOURS`).

## Operational workflows

1. **Agent creation** – The orchestrator calls
   `MailcowProvisioner.create_agent_mailbox(agent_id)` to create the mailbox and
   persists the returned credentials. Immediately after creation the
   `dns_bootstrap.py` script (or the scheduler) refreshes DKIM/SPF/TXT records.
2. **Agent removal** – `delete_agent_mailbox` removes the mailbox and optionally
   its aliases. DNS records remain intact unless explicitly removed.
3. **DynDNS refresh** – A background job triggers `DeSECDNSManager.update_dyndns`
   every `DESEC_UPDATE_INTERVAL_HOURS` hours to keep the IP mapping current.
4. **Inbound processing** – `MailService.fetch_unseen` powers polling loops or
   IMAP IDLE listeners that feed incoming messages to the simulation engine.

## Security notes

* API tokens and app-passwords are injected via environment variables—never
  commit them to the repository.
* Mailcow TLS certificates are handled automatically by ACME; only SMTP SUBMISSION
  (587/465) and IMAP (993) need to be exposed through the firewall.
* Rate limits and quotas guard against runaway agents.
* DKIM/SPF/DMARC enforcement happens before any outbound traffic is sent.

