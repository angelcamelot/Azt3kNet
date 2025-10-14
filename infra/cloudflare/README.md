# Cloudflare Tunnel integration

The optional `cloudflared` service exposes the local FastAPI instance through a
Cloudflare Tunnel while keeping DNS for the apex domain on deSEC. This lets you
serve the API via a `*.dedyn.io` hostname without opening inbound ports on the
host machine.

## Prerequisites

1. Create a free Cloudflare account and enable the **Zero Trust** dashboard.
2. Create a new **Tunnel** (Zero Trust → Networks → Tunnels → *Create tunnel*).
   Cloudflare will generate a long-lived token that can be used by Docker.
3. Add a **Public hostname** for the tunnel and point it to `http://api:8000`
   (or the service URL you prefer). Cloudflare will issue a unique
   `*.cfargotunnel.com` target for the tunnel.
4. In deSEC add a CNAME (for example `api`) that points to the
   `*.cfargotunnel.com` host provided by Cloudflare. The DNS bootstrap script in
   this repository automates the RRset creation when the relevant environment
   variables are defined.

## Environment variables

Populate the following variables in `.env`:

```env
CLOUDFLARE_TUNNEL_TOKEN=<token exported from the Cloudflare dashboard>
CLOUDFLARE_TUNNEL_HOSTNAME=api.azt3knet.dedyn.io
CLOUDFLARE_TUNNEL_SERVICE=http://api:8000
CLOUDFLARE_TUNNEL_CNAME=<uuid>.cfargotunnel.com
CLOUDFLARE_TUNNEL_SUBDOMAIN=api
CLOUDFLARE_TUNNEL_CNAME_TTL=300
```

The DNS bootstrap logic resolves the CNAME subdomain automatically from the
hostname when `CLOUDFLARE_TUNNEL_SUBDOMAIN` is omitted.

## Running the tunnel

Start the main stack together with the `cloudflared` profile:

```bash
docker compose --profile cloudflare up -d
```

The tunnel container executes
`cloudflared tunnel --no-autoupdate run --token $CLOUDFLARE_TUNNEL_TOKEN` and
reuses the existing Docker network so `http://api:8000` resolves to the FastAPI
service.

## DNS bootstrap

When `CLOUDFLARE_TUNNEL_CNAME` is present the helper scripts update the
corresponding CNAME after synchronising Mailjet records:

```bash
poetry run python scripts/dns_bootstrap.py
```

This produces an RRset equivalent to:

```text
api 300 IN CNAME <uuid>.cfargotunnel.com.
```

Combine this with Cloudflare Access policies if you need to protect the API with
Zero Trust rules.
