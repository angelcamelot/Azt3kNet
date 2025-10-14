# Mail automation architecture

This document describes how Azt3kNet provisions real mailboxes for every agent by
combining **Mailjet** (cloud SMTP/API platform with inbound webhooks) with
**Cloudflare** (authoritative DNS and tunnel provider).

## Overview

```
+-----------------+          +----------------------+          +----------------------+
| Azt3kNet Core   |  HTTPS   | Mailjet API          |  HTTPS   | Cloudflare DNS API   |
|  - agent model  +--------->+  /v3/REST/domain     +--------->+  /zones/:id/records  |
|  - orchestrator |          |  /v3/REST/inbound    |          |                      |
+-----------------+          +----------------------+          +----------------------+
         |                            |                                  |
         | SMTP (API key)             | publishes DKIM/SPF               |
         v                            v                                  v
   Agent identity  <--------------- Mailjet SaaS  <---------------  DNS records
         |                                                            (MX/SPF)
         | HTTP webhook delivery                                       |
         v                                                            v
   Inbound processor -----------------------------------------> Azt3kNet events
```

* Mailjet delivers outbound mail via authenticated SMTP/API calls and forwards
  inbound messages to webhooks.
* Cloudflare hosts the public DNS zone and exposes a programmable REST API for
  record management. Optional Cloudflare Tunnel endpoints remove the need for a
  public IP address.
* Azt3kNet modules orchestrate both systems to provide a first-class
  `bot123@domain` identity per agent/bot.

## Configuration

All secrets and endpoints live in the shared `.env` file. See
[`.env.example`](../.env.example) for the full list of variables. The critical
values are:

| Variable | Purpose |
| --- | --- |
| `CLOUDFLARE_API_TOKEN` | Scoped API token with DNS edit permissions. |
| `CLOUDFLARE_ZONE_ID` | Identifier of the Cloudflare zone that hosts the domain. |
| `CLOUDFLARE_ZONE_NAME` | Canonical domain managed in Cloudflare (for example `agents.example`). |
| `MAILJET_API_KEY` / `MAILJET_API_SECRET` | Mailjet API credentials used for SMTP/API authentication. |
| `MAILJET_MX_HOSTS` | Comma separated MX targets delegated to Mailjet (`in.mailjet.com`, `in-v3.mailjet.com`, …). |
| `MAILJET_SPF_INCLUDE` | SPF include directive published in DNS (`include:spf.mailjet.com` by default). |
| `MAILJET_INBOUND_URL` | HTTPS endpoint that receives Mailjet inbound events. |
| `MAILJET_INBOUND_SECRET` | Optional shared secret validated on inbound webhook calls. |
| `AZT3KNET_AGENT_MAIL_PREFIX` | Prefix used when generating agent addresses. |

## Runtime components

### Mail provisioning service

The `MailjetProvisioner` class located in `azt3knet.services.mailjet_provisioner`
wraps the REST API. It can:

* ensure that the sender domain exists in Mailjet and is ready for DKIM signing,
* configure per-address inbound routes that forward messages to our webhook,
* emit credentials (address + SMTP login) for the agent orchestration layer.

### Mailbox naming strategy

Every agent receives a Mailjet identity following the format:

```
<first>.<last>.<random3digits>.<timestamp>@<domain>
```

`<first>` and `<last>` are derived from the agent's legal name (falling back to
the username hint when either component is missing) and sanitized to contain
only lowercase alphanumeric characters. Both segments are truncated to 16
characters to stay within mailbox length limits. The three random digits are
deterministically generated from the population seed to remain reproducible, and
the timestamp corresponds to the current UTC time encoded as `YYYYMMDDHHMMSS`.
This combination keeps addresses human friendly while ensuring uniqueness within
each population build.

If a collision is detected while provisioning a batch (for example, thousands of
agents sharing the exact same name generated on the same second), the builder
retries up to 1,000 deterministic combinations before raising an exception.

Minimal provisioning example:

```python
from azt3knet.core.mail_config import (
    get_mail_provisioning_settings,
    get_mailjet_settings,
)
from azt3knet.services.mailjet_provisioner import MailjetProvisioner

with MailjetProvisioner(
    mailjet=get_mailjet_settings(),
    provisioning=get_mail_provisioning_settings(),
) as provisioner:
    creds = provisioner.create_agent_mailbox(
        agent_id="jane.doe.123.20241005123045",
        display_name="Agent 427",
        apply_prefix=False,
    )
    print(creds.address, creds.smtp_username)
```

### DNS automation

`CloudflareDNSManager` automates DNS record management via the Cloudflare REST
API. It exposes helpers to:

* publish MX, SPF, DKIM and DMARC records using Mailjet-generated keys,
* replace outdated records safely while preserving unrelated TXT entries,
* upsert Cloudflare Tunnel CNAMEs so the API remains reachable without a public
  IP address.

The script `scripts/dns_bootstrap.py` ties both services together: it fetches the
latest DKIM key from Mailjet and updates Cloudflare DNS records accordingly. The
script is designed to run at container startup (via Docker entrypoint or cron).

### Mail access helper

`MailService` is a lightweight SMTP wrapper that converts the mailbox
credentials into `email.message.EmailMessage` instances for sending messages. It
also includes helpers to validate inbound webhook tokens and to parse Mailjet
payloads into structured `EmailMessage` objects for downstream processing.

## Installation guide

### Prerequisites

- A public domain delegated to Cloudflare (for example `agents.example`).
- A Mailjet account with access to the Transactional Email and Inbound routes.
- HTTPS hosting for the inbound webhook endpoint (publicly reachable).
- Python 3.11+ available locally to execute the helper scripts.

### Configure Mailjet

1. Add your domain under **Account > Senders & Domains** in the Mailjet console
   and follow the verification steps. You can skip MX/DKIM setup until the
   Cloudflare integration below is complete.
2. Generate an API key pair (one key/secret per environment) and store it in
   `.env` as `MAILJET_API_KEY` and `MAILJET_API_SECRET`.
3. Determine the MX hosts assigned to your account. The defaults are
   `in.mailjet.com` and `in-v3.mailjet.com`, but Mailjet may provide different
   values. Populate `MAILJET_MX_HOSTS` accordingly.
4. Create (or reuse) an inbound webhook endpoint within your infrastructure and
   expose it publicly. Set `MAILJET_INBOUND_URL` to that URL and optionally set a
   shared secret (`MAILJET_INBOUND_SECRET`).

### Configure Cloudflare DNS

1. Log into the [Cloudflare dashboard](https://dash.cloudflare.com/) and locate
   the zone that hosts your domain.
2. Create an API token under **My Profile → API Tokens** with the
   **Zone.DNS → Edit** permission scoped to the zone above. Store it in `.env` as
   `CLOUDFLARE_API_TOKEN`.
3. Copy the zone identifier from the dashboard and set `CLOUDFLARE_ZONE_ID` in
   `.env`. Ensure `CLOUDFLARE_ZONE_NAME` matches the canonical domain name.

### Bootstrap DNS records

1. Ensure `.env` contains the Mailjet and Cloudflare values described above.
2. Run the bootstrap script locally or inside the Docker stack:

   ```bash
   poetry run python scripts/dns_bootstrap.py
   ```

   The command will:

   - query Mailjet for the DKIM key associated with the domain,
   - publish MX/SPF/DKIM/DMARC records via the Cloudflare API,
   - optionally upsert a Cloudflare Tunnel CNAME when the relevant environment
     variables are set.

3. After DNS changes propagate, finalize the domain verification in the Mailjet
   console. Mailjet should report successful DKIM/SPF checks.

### Cloudflare Tunnel (optional)

Expose the FastAPI surface through Cloudflare while keeping the host machine
fully private:

1. Create a tunnel in the Cloudflare Zero Trust dashboard and add a public
   hostname pointing to `http://api:8000` (or the service URL you prefer).
2. Copy the tunnel token and fill the Cloudflare tunnel variables in `.env`:

   ```env
   CLOUDFLARE_TUNNEL_TOKEN=<token>
   CLOUDFLARE_TUNNEL_HOSTNAME=api.agents.example
   CLOUDFLARE_TUNNEL_SERVICE=http://api:8000
   CLOUDFLARE_TUNNEL_CNAME=<uuid>.cfargotunnel.com
   ```

3. Start Docker with `--profile cloudflare` so the `cloudflared` sidecar joins
   the compose network.
4. Run `scripts/dns_bootstrap.py` to publish the CNAME pointing at the
   Cloudflare tunnel (`api IN CNAME <uuid>.cfargotunnel.com`).

Requests for `https://api.agents.example` now reach Cloudflare, which terminates
TLS and forwards traffic to the Docker network through the tunnel.

### Provision agent identities

Once DNS and Mailjet are configured, call the provisioning APIs (or CLI
commands) to generate mailboxes for every agent. Each agent receives unique
credentials tied to the Mailjet domain and can immediately send/receive email
through the infrastructure described above.
