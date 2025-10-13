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

