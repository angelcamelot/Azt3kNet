# Azt3kNet + deSEC + Mailjet Integration Plan

## Overview

Deliver a deterministic pipeline that generates synthetic populations with full
digital identities, provisions Mailjet-backed mailboxes, and manages DNS via
deSEC. Both the CLI and API should expose the flow end-to-end.
Both the CLI and API should expose the flow end-to-end.

## Commit strategy

1. **Environment scaffolding**
   - Update `pyproject.toml` with the required dependencies (`pydantic`,
     `httpx`, `cryptography`, `typer`, etc.).
   - Add `.env.example` including the new secrets and summarize them in the
     README.
   - Create the initial structure under `src/azt3knet/` for `cli/`, `api/`,
     `services/`, and `adapters/`.
   - Wire the DNS bootstrap service into the Docker stack so Mailjet DNS records
     stay synchronized.

2. **DNS bootstrap and dynamic updates**
   - Implement `infra/dns_bootstrap.py` and `infra/dyn_updater.py` using the
     `dns_manager.py` client for deSEC.
   - Add cron/systemd-lite configuration to run `dyn_updater` on a schedule.
   - Write unit tests for `dns_manager` with `pytest` + `responses`.

3. **LLM adapter and canonical models**
   - Implement `src/azt3knet/llm/adapter.py` with the deterministic
     `generate_field` helper.
   - Consolidate `PopulationSpec` and `AgentProfile` in
     `src/azt3knet/agent_factory/models.py` to avoid duplicates.
   - Add mock-based tests to validate prompts and determinism.

4. **CLI populate (preview mode)**
   - Implement the `azt3knet populate` command in
     `src/azt3knet/cli/populate.py` with flags (`--gender`, `--count`, etc.).
   - Build `population_builder.py` to normalize flags into `PopulationSpec` and
     use the LLM in preview mode without persistence.
   - Document the flow in `docs/cli.md` with practical examples.

5. **Mailbox provisioning and persistence**
   - Implement `src/azt3knet/services/mailjet_provisioner.py` using the Mailjet
     API (`/v3/REST/domain`, `/v3/REST/inbound`) with retries/backoff and
     conflict handling.
   - Integrate password encryption with `SECRET_KEY_FOR_KV_ENC`
     (libsodium/fernet).
   - Add a database repository (`sqlalchemy`/`asyncpg` or the chosen stack) with
     tables `agent_mailbox`, `audit_log`, etc.
   - Extend the CLI/API with `--create-mailboxes` / `create_mailboxes`.
   - Write tests that mock the LLM + Mailjet + DB (including rollbacks).

6. **REST API and recreation script**
   - Add the `POST /api/populate` endpoint with FastAPI (or the current
     framework) and administrative auth.
   - Implement `recreate_from_seed(population_spec, seed)` to re-sync mailboxes
     and DKIM records.
   - Register metrics/logs (audit trail) and a secure credential exporter.
   - Provide lightweight integration tests and documentation.

7. **Documentation and final scripts**
   - Update the README with deployment guidance.
   - Document CLI/API flows, seed handling, and credential security.
   - Add diagrams/templates under `docs/` where appropriate.

## Initial files to create

- `docs/integration_plan.md` (this document).
- `infra/dns_bootstrap.py` (initial skeleton with TODOs).
- `infra/dyn_updater.py` (skeleton).
- `src/azt3knet/dns/dns_manager.py` (placeholder class/interfaces).
- `src/azt3knet/llm/adapter.py` (stub for `generate_field`).
- `src/azt3knet/agent_factory/models.py` (shared dataclasses for agents).
- `src/azt3knet/services/mailjet_provisioner.py` (interface + TODOs).
- `src/azt3knet/population/builder.py` (stub for `build_population`).
- `src/azt3knet/cli/populate.py` (Typer CLI stub).
- `src/azt3knet/api/routes/populate.py` (FastAPI router stub).
- `tests/test_population_preview.py` (placeholder test with TODOs for mocks).
- `tests/conftest.py` (basic fixtures for future tests).

Each scaffolded file should include docstrings and TODOs describing the planned
functionality for later iterations.
