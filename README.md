# 🜂 Azt3kNet

Azt3kNet is a research-oriented Python system that models networks of digital agents within a self-contained environment. All content and populations are generated locally through [Ollama](https://ollama.ai/) and programmatic prompts with deterministic seeds to ensure reproducibility, diversity, and the absence of PII. The platform exposes CLI and API interfaces so other teams (for example, an analytical frontend) can orchestrate population creation, content generation, and feed simulations under strict ethics and compliance policies.

## 🚀 Key Capabilities

- **Synthetic population generation** from parameterized specifications (gender, location, age, interests) transformed into structured prompts for Ollama.
- **DeepSeek-powered identity crafting** so every agent receives a unique name generated locally with the lightweight `deepseek-r1:1.5b` Ollama model.
- **Controlled Content Engine** that produces drafts, captions, alt-text, hashtags, and variations with explanatory metadata and compliance scores.
- **Feed simulator** that orchestrates posts, comments, reactions, and conversation chains with a configurable affinity graph.
- **Always-on Compliance Guard** that labels or blocks risky content and audits every decision.
- **End-to-end observability** with structured logging, Prometheus metrics, and OpenTelemetry traces.
- **Pluggable persistence** (SQLite/Postgres) with Alembic migrations and JSON/CSV exports for frontends.

## 📁 Repository Layout

```
.
├── README.md
├── docs/
│   ├── ARCHITECTURE.md         # Deep dive into the proposed architecture
│   ├── mail-architecture.md    # Mailcow + deSEC automation plan
│   ├── ADRs/                   # Architecture decision records
│   └── diagrams/               # Component/flow diagrams
├── infra/
│   ├── docker/                 # Dockerfiles, docker-compose, and environment scripts
│   ├── migrations/             # Alembic environment + versions
│   └── observability/          # Prometheus/OTel configuration
├── scripts/                    # Bootstrap utilities and developer tools
├── src/azt3knet/
│   ├── __init__.py
│   ├── adapters/               # Mocks of external platforms
│   ├── agent_factory/          # Agent generation and export
│   ├── api/                    # FastAPI routers and dependencies
│   ├── cli/                    # Typer interface `azt3knet`
│   ├── compliance_guard/       # Rules, classifiers, and auditing
│   ├── content_engine/         # Templates and content pipeline
│   ├── core/                   # Config, logging, metrics, traces, prompts
│   ├── infra/                  # Settings, secrets, queue providers
│   ├── orchestrator/           # Workflow coordination and affinities
│   ├── scheduler/              # Job runner/queue (Arq/Celery)
│   ├── simulation/             # Feed engine and reports
│   └── storage/                # SQLAlchemy, repositories, UoW
└── tests/
    ├── unit/
    ├── integration/
    ├── simulation/
    └── golden/
```

## 🧠 Core Components

| Module | Role | Highlights |
|--------|-----|------------|
| `core` | Centralized configuration, deterministic seeds, observability utilities, and prompt templates | `pydantic-settings`, `structlog`, `opentelemetry`, `prometheus_client` |
| `agent_factory` | Normalizes specifications, generates agents via Ollama, and handles persistence/export | Pydantic schemas (`AgentProfile`), diversity validation, JSON/CSV fixtures |
| `content_engine` | Orchestrates templates + agent context to produce drafts and variations with metadata and `compliance_score` | Asynchronous Ollama client, seed-based pipeline |
| `scheduler` | Background job management (`population`, `content`, `simulation`) with retries, rate limiting, and monitoring | `Arq`/`Celery`, `asyncio.TaskGroup` |
| `orchestrator` | Coordinates who posts, when, and with what affinities; integrates compliance and storage | Affinity graph, simulation events |
| `simulation` | Feed engine emitting posts, comments, likes, and reproducible reply chains | Scenario metrics, audit reports |
| `compliance_guard` | Applies safety rules, classifies risks, and documents decisions | Declarative rules, local heuristics, persisted auditing |
| `storage` | Persistence layer with SQLAlchemy 2.0, Alembic migrations, repositories, and UoW | SQLite/Postgres, job/agent/content records |
| `api` | FastAPI surface mirroring the CLI and exposing metrics | `population`, `content`, `simulation`, `jobs`, `health` routers |
| `cli` | Typer commands `azt3knet` covering every main flow | Flags aligned with the API |
| `adapters` | Social feed and messaging stubs/mocks that let frontends connect without touching real services | Documented contracts |

## 🧾 Synthetic Agent Schema

Every Ollama response must return exactly **N** unique records following this Pydantic schema:

```python
class AgentProfile(BaseModel):
    id: UUID4
    seed: str
    name: str
    username_hint: str
    country: str
    city: str
    locale: str
    timezone: str
    age: conint(ge=13, le=90)
    gender: Literal["female", "male", "non_binary", "unspecified"]
    interests: List[str]
    bio: str
    posting_cadence: Literal["hourly", "daily", "weekly", "monthly"]
    tone: Literal["casual", "formal", "enthusiastic", "sarcastic", "informative"]
    behavioral_biases: List[str]
```

- `seed` derives deterministically from the population specification and the agent index.
- `interests`, `bio`, and `behavioral_biases` exclude PII and references to real accounts.
- `agent_factory` validates `username_hint` uniqueness, gender/interest diversity, and geographic consistency.

## 📊 Population Specification

Populations are defined via CLI or API using the same parameters. CLI example:

```bash
azt3knet populate \
  --gender female \
  --count 1000 \
  --country MX \
  --city "Mexico City" \
  --age 18-25 \
  --interests "street art,urban culture" \
  --seed 20241005 \
  --preview 10
```

API equivalent:

```http
POST /api/populate
{
  "gender": "female",
  "count": 1000,
  "country": "MX",
  "city": "Mexico City",
  "age_range": [18, 25],
  "interests": ["street art", "urban culture"],
  "seed": "20241005",
  "preview": 10
}
```

| Field | Type | Required | Description |
|-------|------|-----------|-------------|
| `gender` | `female` \| `male` \| `non_binary` \| `unspecified` | Yes | Base gender filter. |
| `count` | integer > 0 | Yes | Number of agents to generate. |
| `country` | ISO 3166-1 alpha-2 | Yes | Simulated country of residence. |
| `city` | text | Optional | Specific city (uses composite seeds). |
| `age_range` | `[min, max]` | Optional | Both bounds inclusive, 13 ≤ age ≤ 90. |
| `interests` | list of strings | Optional | Must contain ≥ 1 interest if provided. |
| `seed` | string | Optional | Drives reproducibility; auto-generated if missing. |
| `preview` | integer | Optional | Shows N records without persisting. |
| `persist` | bool | Optional | If `true`, saves to storage and returns a `job_id`. |

Specifications are transformed into programmatic, precise prompts for Ollama that demand N unique records adhering to the schema above and compliance policies.

## 🔁 CLI and API Flows

| Action | CLI | API | Outcome |
|--------|-----|-----|---------|
| Generate population | `azt3knet populate ...` | `POST /api/populate` | Enqueues a job in the `population` queue, optionally previews and/or persists. |
| Export fixtures | `azt3knet populate ... --persist --export json --path data/fixtures/mx.json` | `POST /api/populate?export=json` | Produces JSON/CSV fixtures for frontends. |
| Create content | `azt3knet content draft --agent <uuid> --template street_art_campaign` | `POST /api/content/draft` | Returns drafts, captions, alt-text, hashtags, variations + metadata and `compliance_score`. |
| Run simulation | `azt3knet sim run --scenario metro_cdmx --ticks 120` | `POST /api/simulations/{scenario}/run` | Enqueues a feed simulation job, exposes metrics and reports. |
| Job status | `azt3knet jobs status <id>` | `GET /api/jobs/{id}` | Returns status (`queued`, `running`, `failed`, `completed`) and metadata. |
| Health/observability | `azt3knet system check` | `GET /healthz`, `GET /metrics` | Healthcheck + Prometheus metrics. |

All commands accept a global `--seed` for reproducibility. The API returns a `job_id` and links to exports when applicable.

## ⚙️ Background Work and Observability

- **Job runner/queue:** `scheduler` encapsulates Arq (preferred) or Celery with Redis. Separate queues (`population`, `content`, `simulation`) isolate workloads.
- **Structured logging:** JSON with fields `job_id`, `agent_id`, `seed`, `scenario`. Integration with `core.logging`.
- **Prometheus metrics:** generation times, retry rate, population sizes, compliance ratios, events per scenario.
- **OpenTelemetry traces:** spans for CLI/API, workers, Ollama calls, and storage. Configurable through `core.tracing`.

## 🗄️ Persistence and Migrations

- **Pluggable storage:** SQLite for rapid development; Postgres recommended for integrated testing.
- **Alembic:** migrations live in `infra/migrations`, runnable from the CLI (`azt3knet db upgrade`).
- **Repositories and UoW:** `storage.repositories` and `storage.unit_of_work` isolate transactions and simplify testing.
- **Exports:** `agent_factory.export` produces deterministic JSON/CSV ready for frontends or offline analysis.

## 🧪 Testing Strategy

- **Unit tests:** validate Pydantic schemas, prompt formatting, deterministic seeds, compliance rules.
- **Integration tests:** end-to-end pipelines mocking Ollama with golden fixtures and spinning up Redis/Postgres via Docker.
- **Golden tests:** snapshots of populations/content for known seeds (`tests/golden`) guarantee stability.
- **Simulation tests:** reproducible scenarios verify affinity and activity metrics. Reply chains are compared against fixtures.
- **Compliance tests:** inject adversarial content and confirm that `ComplianceGuard` blocks, labels, and audits correctly.

Example test command:

```bash
poetry run pytest
```

## 🧯 Ethics and Compliance Policies

1. **Transparency and traceability.** Every generation records the `seed`, prompts used, compliance decisions, and metrics.
2. **Proactive moderation.** Risky content is blocked or labeled and never published without explicit review.
3. **Responsible LLM usage.** Ollama runs locally; model versions and parameters are documented.

## 🔧 Getting Started (Summary)

### Docker quick start

1. Bootstrap the environment files (creates `.env` and `infra/docker/.env`):

   ```bash
   ./scripts/bootstrap_env.sh
   ```

2. Start the full stack (API + Postgres + Redis + Ollama) in the background:

   ```bash
   ./scripts/dev_up.sh
   ```

## ✉️ Mail infrastructure

The project ships with a full automation layer for Mailcow (mail server) and
deSEC (DNSSEC-enabled dynamic DNS). Review [`docs/mail-architecture.md`](docs/mail-architecture.md)
for the detailed blueprint, environment variables and bootstrap scripts. Core
modules live under `azt3knet.services` and expose:

* `MailcowProvisioner` – REST client that creates/updates agent mailboxes and
  app-passwords.
* `DeSECDNSManager` – ensures MX/SPF/DKIM/DMARC records exist and keeps DynDNS
  assignments fresh.
* `MailService` – SMTP/IMAP convenience wrapper to send and fetch emails per
  agent.

3. Pull the Ollama model the first time you run the stack (replace
   `deepseek-r1:1.5b` with the value you configured in `infra/docker/.env`):

   ```bash
   docker compose exec ollama ollama pull deepseek-r1:1.5b
   ```

4. The API is now available at [http://localhost:8000](http://localhost:8000).
   To generate a preview population via the CLI inside the container, run:

   ```bash
   docker compose run --rm api azt3knet populate --gender female --count 10 --country MX --preview 3
   ```

5. When finished, shut everything down and remove containers with:

   ```bash
   ./scripts/dev_down.sh
   ```

The compose file mounts the repository into the container and runs
Uvicorn in reload mode, so code changes are reflected immediately.

### Manual setup

1. Install [Ollama](https://ollama.ai/) and download the required model (`ollama pull <model>`).
2. Copy the provided environment templates and adjust them to your workstation:

   ```bash
   ./scripts/bootstrap_env.sh
   ```

   This command creates `.env` and `infra/docker/.env` from their respective templates.

   The application inspects `AZT3KNET_ENVIRONMENT` and `AZT3KNET_COMPLIANCE_ENABLED` at startup. Override them in your shell or `.env` file to switch between environments or toggle compliance behavior:

   ```bash
   export AZT3KNET_ENVIRONMENT=staging
   export AZT3KNET_COMPLIANCE_ENABLED=false
   ```

3. Set up the Python environment (e.g., `poetry install`).
4. Start auxiliary services (Redis/Postgres/Ollama) with `./scripts/dev_up.sh postgres redis ollama`.
5. Run migrations (`azt3knet db upgrade`).
6. Launch the API (`poetry run uvicorn azt3knet.api.main:app --reload`) and worker (`poetry run azt3knet worker`).
7. Use the CLI/API according to the flows above.

### Sprint 1 (Functional Inception)

The first sprint delivers the foundations for deterministic synthetic populations:

- **Shared configuration** powered by Pydantic settings and deterministic seed helpers.
- **Agent factory** that generates reproducible `AgentProfile` records from population specs.
- **CLI command** `azt3knet populate` for local experimentation with preview limits and JSON output.
- **FastAPI endpoint** `POST /api/populate` mirroring the CLI surface for orchestration prototypes.
- **Basic observability hooks** (`configure_logging`) to maintain consistent logs across surfaces.

Run the included tests to validate determinism and interfaces:

```bash
poetry install
poetry run pytest
```

## 🤝 Contributing

- Follow linting and type-checking conventions (`ruff`, `mypy`).
- Add/update tests, especially golden tests when prompts or templates change.
- Document new decisions in `docs/ADRs/`.
- Every contribution must uphold the core premise: local simulation, synthetic data, strict compliance.

---

Azt3kNet offers a safe laboratory for experimenting with networks of digital agents. Thanks to deterministic seeds, comprehensive observability, and transparent compliance, the system enables responsible iteration without approaching real-account automation.
