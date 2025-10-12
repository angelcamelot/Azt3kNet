# Azt3kNet Architecture Blueprint

This document defines the recommended end-state architecture for **Azt3kNet**, an AI-driven bot network orchestration system. The structure prioritizes clarity, scalability, maintainability, and extensibility, and it supersedes any previous documentation.

## Repository Layout

```
.
├── Makefile
├── README.md
├── docs/
│   ├── ARCHITECTURE.md
│   ├── ADRs/
│   │   └── README.md
│   └── diagrams/
│       └── system-context.drawio
├── infra/
│   ├── docker/
│   │   ├── Dockerfile.api
│   │   ├── Dockerfile.worker
│   │   └── docker-compose.yml
│   ├── helm/
│   └── terraform/
├── scripts/
│   ├── bootstrap_env.py
│   └── manage.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── integration/
│   ├── load/
│   └── unit/
└── src/
    └── azt3knet/
        ├── __init__.py
        ├── api/
        │   ├── __init__.py
        │   ├── dependencies.py
        │   ├── routers/
        │   │   ├── __init__.py
        │   │   ├── agents.py
        │   │   ├── orchestrator.py
        │   │   ├── scheduler.py
        │   │   └── status.py
        │   └── websocket.py
        ├── cli/
        │   ├── __init__.py
        │   └── main.py
        ├── compliance_guard/
        │   ├── __init__.py
        │   ├── classifiers.py
        │   ├── policies.py
        │   └── pipeline.py
        ├── config/
        │   ├── __init__.py
        │   ├── settings.py
        │   └── secrets.py
        ├── content_engine/
        │   ├── __init__.py
        │   ├── generators/
        │   │   ├── base.py
        │   │   ├── llm.py
        │   │   └── templating.py
        │   ├── scoring.py
        │   ├── template_store.py
        │   └── workflows.py
        ├── core/
        │   ├── __init__.py
        │   ├── events.py
        │   ├── exceptions.py
        │   ├── interfaces.py
        │   ├── logging.py
        │   ├── messaging.py
        │   └── utils.py
        ├── integration/
        │   ├── __init__.py
        │   ├── mailbox.py
        │   ├── platforms/
        │   │   ├── __init__.py
        │   │   ├── base.py
        │   │   ├── social_stub.py
        │   │   └── webhooks.py
        │   └── webhooks.py
        ├── orchestrator/
        │   ├── __init__.py
        │   ├── coordinator.py
        │   ├── state.py
        │   └── workflows.py
        ├── agent_factory/
        │   ├── __init__.py
        │   ├── identity.py
        │   ├── metadata.py
        │   └── registry.py
        ├── scheduler/
        │   ├── __init__.py
        │   ├── dispatcher.py
        │   ├── rate_limiter.py
        │   └── tasks.py
        ├── simulation/
        │   ├── __init__.py
        │   ├── environment.py
        │   ├── feed.py
        │   ├── metrics.py
        │   └── scenario.py
        ├── storage/
        │   ├── __init__.py
        │   ├── db.py
        │   ├── models/
        │   │   ├── __init__.py
        │   │   ├── agent.py
        │   │   ├── content.py
        │   │   ├── event.py
        │   │   └── job.py
        │   ├── repositories/
        │   │   ├── __init__.py
        │   │   ├── agents.py
        │   │   ├── content.py
        │   │   ├── events.py
        │   │   └── jobs.py
        │   └── unit_of_work.py
        ├── worker/
        │   ├── __init__.py
        │   └── tasks.py
        └── workflows/
            ├── __init__.py
            ├── content_publication.py
            ├── lifecycle.py
            └── moderation.py
```

## Module Overview and Responsibilities

### `api`
- **Purpose:** Provide a clean command-and-control surface over REST and WebSocket APIs using FastAPI.
- **Key Components:**
  - `routers`: REST endpoints for orchestrator control, agent lifecycle, scheduling status, and health.
  - `dependencies`: Pydantic-based request/response models, dependency injection wiring.
  - `websocket`: Event bus streaming orchestrator events to dashboards or integrations.
- **Technologies:** FastAPI, Pydantic v2, Starlette WebSockets, AsyncAPI documentation.

### `cli`
- **Purpose:** Offer operational tooling for bootstrapping data, running simulations, and invoking orchestrator commands.
- **Key Components:** `main.py` defines Typer-based CLI commands for provisioning identities, seeding templates, running scenarios, and invoking maintenance scripts.
- **Technologies:** Typer, Rich for output formatting.

### `core`
- **Purpose:** House cross-cutting primitives and infrastructure abstractions.
- **Key Components:**
  - `events`: Internal event definitions using Pydantic models and typed channels.
  - `messaging`: Abstractions for message buses (Redis Streams, NATS, or RabbitMQ) and in-memory fallback.
  - `logging`: Structured logging setup with structlog and OpenTelemetry integration.
  - `interfaces`: Protocol definitions for pluggable services (content generation, storage, compliance).
  - `utils`: Shared helpers, feature flags, resilience utilities (retry/backoff).
- **Technologies:** structlog, OpenTelemetry, tenacity.

### `config`
- **Purpose:** Centralize configuration, secrets management, and environment handling.
- **Key Components:**
  - `settings.py`: Environment-aware `BaseSettings` with layered overrides (env vars, `.env`, Vault/SSM).
  - `secrets.py`: Interface to secret stores (HashiCorp Vault, AWS Secrets Manager).
- **Technologies:** Pydantic Settings, python-dotenv, hvac/boto3 (optional).

### `orchestrator`
- **Purpose:** Coordinate agent workflows, manage lifecycles, and dispatch tasks to downstream components.
- **Key Components:**
  - `coordinator.py`: Central orchestrator state machine handling agent activation, monitoring, and event dispatch.
  - `state.py`: Domain models for agent sessions, campaigns, and orchestration contexts.
  - `workflows.py`: High-level orchestrations for onboarding, content generation, compliance review, and publishing.
- **Technologies:** asyncio, fastapi background tasks, Celery/Arq for distributed job offloading.

### `agent_factory`
- **Purpose:** Generate and manage bot identities with persistent metadata and bot templates.
- **Key Components:**
  - `identity.py`: Bot identity synthesis logic using prompt templates and demographic datasets.
  - `metadata.py`: Persistent metadata schema, enrichment, and validation.
  - `registry.py`: Registry of available agent blueprints and provisioning pipeline hooks.
- **Technologies:** Faker, synthetic data generators, SQLAlchemy models, possibly graph-based relationships.

### `content_engine`
- **Purpose:** Produce content drafts, score them, and run compliance checks.
- **Key Components:**
  - `generators/`: pluggable content generation backends (OpenAI, local LLMs, rule-based templates).
  - `scoring.py`: Quality scoring, sentiment analysis, toxicity detection.
  - `template_store.py`: Versioned template repository with Jinja2/Prompt interpolation.
  - `workflows.py`: Multi-step pipeline combining generation, scoring, compliance gating.
- **Technologies:** LangChain/LlamaIndex, OpenAI/transformers, Hugging Face pipelines, Jinja2.

### `compliance_guard`
- **Purpose:** Apply policy and legal constraints before publishing content.
- **Key Components:**
  - `policies.py`: Declarative policy definitions with rule metadata.
  - `pipeline.py`: Execution pipeline chaining classifiers and manual review steps.
  - `classifiers.py`: Integrations for moderation APIs and in-house models.
- **Technologies:** Pydantic models, spaCy/textstat, OpenAI moderation, custom heuristics.

### `scheduler`
- **Purpose:** Rate-limited scheduling, approvals, and publishing orchestration.
- **Key Components:**
  - `dispatcher.py`: Async scheduler that enqueues tasks respecting platform quotas.
  - `rate_limiter.py`: Token-bucket or leaky-bucket implementation with Redis backend.
  - `tasks.py`: Celery/Arq task definitions for publishing, approvals, reminders.
- **Technologies:** APScheduler or dramatiq, Redis, Celery/Arq.

### `storage`
- **Purpose:** Provide persistence with modular backends.
- **Key Components:**
  - `db.py`: Database engine setup supporting Postgres + SQLite for dev.
  - `models/`: SQLAlchemy ORM models, plus hybrid JSON storage for unstructured data.
  - `repositories/`: Repository pattern for domain operations.
  - `unit_of_work.py`: Transactional boundary for orchestrator workflows.
- **Technologies:** SQLAlchemy 2.0, Alembic migrations, Pydantic schemas, s3fs/minio for blob storage.

### `simulation`
- **Purpose:** Simulate feeds, interactions, and multi-agent scenarios.
- **Key Components:**
  - `environment.py`: Simulation runtime for running scenarios.
  - `feed.py`: Models a social feed with engagement mechanics.
  - `metrics.py`: KPIs and telemetry for measuring outcomes.
  - `scenario.py`: High-level scenario definitions for load testing and experimentation.
- **Technologies:** asyncio event loops, networkx for relationship graphs, Mesa or custom simulation engine.

### `integration`
- **Purpose:** Adapters for external systems (social platforms, email, messaging, analytics).
- **Key Components:**
  - `mailbox.py`: IMAP/SMTP stubs for agent inbox management.
  - `platforms/`: Platform adapters with publish/reply APIs and webhook handlers.
  - `webhooks.py`: Shared webhook validation utilities.
- **Technologies:** HTTPX, aiobotocore, platform SDKs.

### `worker`
- **Purpose:** Background task runner entry points for Celery/Arq workers.
- **Key Components:** `tasks.py` wires orchestrator workflows, content generation, compliance checks, and scheduler tasks to async job queue.
- **Technologies:** Celery with Redis/RabbitMQ, or Arq with Redis.

### `workflows`
- **Purpose:** Higher-level orchestration pipelines composed across modules.
- **Key Components:** Domain-specific flows: content publication, lifecycle management, moderation escalations.
- **Technologies:** Prefect, Temporal, or custom async orchestrations leveraging `asyncio.TaskGroup`.

## System-Level Components

### Configuration Management
- Layered settings using Pydantic Settings.
- Secrets retrieved at runtime via `secrets.py` abstraction with support for local `.env`, Vault, AWS SSM.
- Configuration profiles (development, staging, production) stored in `config/settings.yaml` with overrides.

### Logging & Observability
- Structured logging with `structlog` and context-aware loggers.
- OpenTelemetry instrumentation for tracing asynchronous workflows.
- Metrics exported via Prometheus client; dashboards defined in `infra/observability/` (future addition).

### Event and Messaging Fabric
- Internal event system defined in `core.events` with typed channels.
- Messaging adapters to Redis Streams, NATS JetStream, or RabbitMQ; default in-memory queue for tests.
- Event bus powers orchestrator notifications, scheduler events, and WebSocket updates.

### Persistence Strategy
- Primary relational database (PostgreSQL) managed through SQLAlchemy ORM and Alembic migrations.
- JSON document store for agent state snapshots (MongoDB or Postgres JSONB) behind repository abstraction.
- Blob storage interface for media assets (S3-compatible).

### API & External Access
- FastAPI application exposing orchestrator control endpoints and streaming event bus.
- Authentication via OAuth2 (client credentials) or API keys.
- Rate limiting using Redis-based middleware.
- Automatic documentation with OpenAPI + AsyncAPI specs.

### Job Processing & Scheduling
- Celery/Arq worker fleet consuming orchestrator, content generation, compliance, and publishing tasks.
- APScheduler-based cron for periodic maintenance (reconciliation, cleanups).
- Rate limiter ensures platform quotas are respected via Redis token buckets.

### Simulation & Experimentation
- CLI triggers simulation scenarios for multi-agent interactions.
- Simulation metrics recorded in storage for comparison against real-world outcomes.

## MVP Functional Plan

1. **Bot Identity Generation**
   - `agent_factory.identity`: Create bots via templates and data augmentation.
   - Persist metadata via `storage.repositories.agents`.
   - Expose provisioning API endpoint `/agents/provision` and CLI command `azt3knet agents provision`.

2. **Content Generation**
   - `content_engine.workflows`: Pipeline generating drafts using LLM providers.
   - Scoring via `content_engine.scoring`; compliance via `compliance_guard.pipeline`.
   - Store drafts, scores, compliance decisions in `storage.repositories.content`.

3. **Feed Simulation**
   - `simulation.feed` & `simulation.environment`: Replay content interactions among agents.
   - Use CLI to trigger scenarios and produce metrics reports.

4. **Rate-Limited Scheduler**
   - `scheduler.dispatcher`: Enqueue publish jobs with rate limiter enforced.
   - Worker tasks push to integration adapters when approved.

5. **Mailbox & Integrations**
   - `integration.mailbox` stubs for email/inbox flows.
   - Platform adapters for posting content (initially stubbed or local sandbox).

## Testing & Quality Strategy

- `tests/unit`: Fast pytest coverage with async test utilities and fixtures mocking external services.
- `tests/integration`: Spin up Postgres, Redis, and worker containers using pytest-docker.
- `tests/load`: Stress tests for scheduler and orchestrator concurrency.
- Use `pytest-asyncio`, `hypothesis` for property-based tests, and `factory-boy` for fixtures.

### CI/CD Pipeline
- GitHub Actions workflow (`.github/workflows/ci.yml`) running:
  1. Lint (ruff + mypy).
  2. Unit tests (pytest).
  3. Integration tests (docker-compose services).
  4. Build/publish Docker images.
- Deploy pipeline triggered on main merges, using Terraform/Helm templates under `infra/`.

### Environment Management
- `pyproject.toml` managed by Poetry for dependency grouping (core, api, worker, simulation extras).
- `Makefile` shortcuts: `make setup`, `make lint`, `make test`, `make run-api`, `make run-worker`, `make sim`.
- `scripts/bootstrap_env.py` seeds dev databases, loads templates, and configures secrets.
- Docker Compose for local stack with Postgres, Redis, MinIO, and worker.

## Future Scalability Considerations

- **Multi-Agent Simulations:** Extend `simulation` with reinforcement learning policies, enabling self-play and automated strategy tuning.
- **Dashboards:** Build a React or Streamlit dashboard consuming WebSocket events for monitoring campaigns in real-time.
- **AI-Driven Orchestration:** Apply reinforcement learning or planner agents within `orchestrator.workflows` to autonomously adjust strategies based on outcomes.
- **Temporal Workflows:** Consider migrating orchestrations to Temporal.io for reliable, stateful workflows across distributed workers.
- **Federated Storage:** Partition storage layer with sharded Postgres or multi-region data stores to scale large campaigns.
- **Policy Automation:** Add dynamic policy updates from compliance feeds and apply diff-based rollout with audit trails.

---

This blueprint should serve as the foundation for implementing Azt3kNet with best-in-class architecture and maintainable code organization.
