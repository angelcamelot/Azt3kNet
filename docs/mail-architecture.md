# Mail automation architecture

This document describes how Azt3kNet provisions real mailboxes for every agent by
combining **Mailjet** (cloud SMTP/API platform with inbound webhooks) with
**deSEC** (DNSSEC-enabled DynDNS provider).

## Overview

```
+-----------------+          +----------------------+          +------------------+
| Azt3kNet Core   |  HTTPS   | Mailjet API          |  HTTPS   | deSEC API        |
|  - agent model  +--------->+  /v3/REST/domain     +--------->+  /domains/...    |
|  - orchestrator |          |  /v3/REST/inbound    |          |  DynDNS          |
+-----------------+          +----------------------+          +------------------+
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
* deSEC hosts the public DNS zone and offers a DynDNS endpoint to keep the
  `dedyn.io` hostname pointing to the current public IP address.
* Azt3kNet modules orchestrate both systems to provide a first-class
  `bot123@domain` identity per agent/bot.

## Configuration

All secrets and endpoints live in the shared `.env` file. See
[`.env.example`](../.env.example) for the full list of variables. The critical
values are:

| Variable | Purpose |
| --- | --- |
| `DESEC_DOMAIN` | Base dedyn.io domain managed in deSEC |
| `DESEC_TOKEN` | API token with RRset and DynDNS scopes |
| `MAILJET_API_KEY` / `MAILJET_API_SECRET` | Mailjet API credentials used for SMTP/API authentication |
| `MAILJET_MX_HOSTS` | Comma separated MX targets delegated to Mailjet (`in.mailjet.com`, `in-v3.mailjet.com`, ...)|
| `MAILJET_SPF_INCLUDE` | SPF include directive published in DNS (`include:spf.mailjet.com` by default) |
| `MAILJET_INBOUND_URL` | HTTPS endpoint that receives Mailjet inbound events |
| `MAILJET_INBOUND_SECRET` | Optional shared secret validated on inbound webhook calls |
| `AZT3KNET_AGENT_MAIL_PREFIX` | Prefix used when generating agent addresses |

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

`DeSECDNSManager` automates RRset management and DynDNS updates via the deSEC
API. It exposes helpers to:

* bulk upsert MX, SPF, DKIM and DMARC records using Mailjet-generated keys,
* optionally maintain a `mail.<domain>` A record that points to the current
  public IP (used by legacy tooling),
* call `https://update.dedyn.io` with token authentication to refresh the
  dynamic DNS assignment every 24 hours (configurable).

The script `scripts/dns_bootstrap.py` ties both services together: it fetches the
latest DKIM key from Mailjet, discovers the public IP, updates DNS RRsets and
triggers a DynDNS refresh. This script is designed to run at container startup
(via Docker entrypoint or cron).

### Mail access helper

`MailService` is a lightweight SMTP wrapper that converts the mailbox
credentials into `email.message.EmailMessage` instances for sending messages. It
also includes helpers to validate inbound webhook tokens and to parse Mailjet
payloads into structured `EmailMessage` objects for downstream processing.

## Installation guide

### Prerequisites

- A public domain delegated to deSEC (for example `your-prefix.dedyn.io`).
- A Mailjet account with access to the Transactional Email and Inbound routes.
- HTTPS hosting for the inbound webhook endpoint (publicly reachable).
- Python 3.11+ available locally to execute the helper scripts.

### Configure Mailjet

1. Add your domain under **Account > Senders & Domains** in the Mailjet console
   and follow the verification steps. You can skip MX/DKIM setup until the deSEC
   integration below is complete.
2. Generate an API key pair (one key/secret per environment) and store it in
   `.env` as `MAILJET_API_KEY` and `MAILJET_API_SECRET`.
3. Determine the MX hosts assigned to your account. The defaults are
   `in.mailjet.com` and `in-v3.mailjet.com`, but Mailjet may provide different
   values. Populate `MAILJET_MX_HOSTS` accordingly.
4. Create (or reuse) an inbound webhook endpoint within your infrastructure and
   expose it publicly. Set `MAILJET_INBOUND_URL` to that URL and optionally set a
   shared secret (`MAILJET_INBOUND_SECRET`).

### Configure deSEC DynDNS

1. Create an account at [https://desec.io](https://desec.io) and add your
   hostname (for example `your-prefix.dedyn.io`). Enable DynDNS for the domain.
2. Generate an API token with RRset read/write permissions and DynDNS access.
   Store it in `.env` as `DESEC_TOKEN`.
3. Set `DESEC_DOMAIN` to the managed hostname (for example `your-prefix.dedyn.io`).
   Optionally override `DESEC_DYNDNS_UPDATE_URL` if you use a custom endpoint.

### Bootstrap DNS records

1. Ensure `.env` contains the Mailjet and deSEC values described above.
2. Run the bootstrap script locally or inside the Docker stack:

   ```bash
   poetry run python scripts/dns_bootstrap.py
   ```

   The command will:

   - query Mailjet for the DKIM key associated with the domain,
   - publish MX/SPF/DKIM/DMARC records via the deSEC API,
   - update the dynamic DNS entry with the current public IP.

3. After DNS changes propagate, finalize the domain verification in the Mailjet
   console. Mailjet should report successful DKIM/SPF checks.

### Provision agent identities

Invoke the CLI with the `--create-mailboxes` flag to provision Mailjet identities
alongside the population preview:

```bash
poetry run azt3knet populate --count 5 --country ES --create-mailboxes
```

The command prints both the generated agents and their corresponding SMTP
credentials. Inbound routes are automatically created for each new address and
point to the webhook configured via `MAILJET_INBOUND_URL`.
