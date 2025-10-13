# 🜂 Azt3kNet

> **Azt3kNet es una simulación local con datos 100 % sintéticos.** Nunca automatiza cuentas reales ni interactúa con plataformas externas.

Azt3kNet es un sistema Python orientado a investigación que modela redes de agentes digitales dentro de un entorno autocontenido. Todo el contenido y las poblaciones se generan localmente mediante [Ollama](https://ollama.ai/) y prompts programáticos con semillas deterministas para garantizar reproducibilidad, diversidad y ausencia de PII. La plataforma expone interfaces CLI y API para que otros equipos (por ejemplo, un frontend analítico) orquesten la creación de poblaciones, generación de contenido y simulaciones de feed bajo estrictas políticas de ética y cumplimiento.

## 🚀 Capacidades clave

- **Generación de poblaciones sintéticas** a partir de especificaciones parametrizadas (género, ubicación, edad, intereses) transformadas en prompts estructurados para Ollama.
- **Content Engine controlado** que produce borradores, captions, alt-text, hashtags y variaciones con metadatos explicativos y puntajes de cumplimiento.
- **Simulador de feed** que orquesta publicaciones, comentarios, reacciones y cadenas conversacionales con un grafo de afinidades configurable.
- **Compliance Guard siempre activo** que etiqueta o bloquea contenido riesgoso y audita cada decisión.
- **Observabilidad integral** con logging estructurado, métricas Prometheus y trazas OpenTelemetry.
- **Persistencia pluggable** (SQLite/Postgres) con migraciones Alembic y exportaciones JSON/CSV para frontends.

## 📁 Disposición del repositorio

```
.
├── README.md
├── docs/
│   ├── ARCHITECTURE.md         # Profundiza en la arquitectura propuesta
│   ├── ADRs/                   # Registros de decisiones de arquitectura
│   └── diagrams/               # Diagramas de componentes/flujo
├── infra/
│   ├── docker/                 # Dockerfiles, docker-compose y scripts de entorno
│   ├── migrations/             # Entorno Alembic + versiones
│   └── observability/          # Configuración Prometheus/OTel
├── scripts/                    # Utilidades de bootstrap y herramientas dev
├── src/azt3knet/
│   ├── __init__.py
│   ├── adapters/               # Mocks de plataformas externas
│   ├── agent_factory/          # Generación y exportación de agentes
│   ├── api/                    # FastAPI routers y dependencias
│   ├── cli/                    # Interfaz Typer `azt3knet`
│   ├── compliance_guard/       # Reglas, clasificadores y auditoría
│   ├── content_engine/         # Plantillas y pipeline de contenido
│   ├── core/                   # Config, logging, métricas, trazas, prompts
│   ├── infra/                  # Settings, secrets, proveedores de colas
│   ├── orchestrator/           # Coordinación de workflows y afinidades
│   ├── scheduler/              # Job runner/queue (Arq/Celery)
│   ├── simulation/             # Motor de feed y reportes
│   └── storage/                # SQLAlchemy, repositorios, UoW
└── tests/
    ├── unit/
    ├── integration/
    ├── simulation/
    └── golden/
```

## 🧠 Componentes principales

| Módulo | Rol | Destacados |
|--------|-----|------------|
| `core` | Configuración centralizada, seeds deterministas, utilidades de observabilidad y plantillas de prompts | `pydantic-settings`, `structlog`, `opentelemetry`, `prometheus_client` |
| `agent_factory` | Normaliza especificaciones, genera agentes vía Ollama y maneja persistencia/exportación | Pydantic schemas (`AgentProfile`), validación de diversidad, fixtures JSON/CSV |
| `content_engine` | Orquesta plantillas + contexto de agente para producir borradores y variaciones con metadatos y `compliance_score` | Cliente Ollama asincrónico, pipeline basado en seeds |
| `scheduler` | Gestión de trabajos de fondo (`population`, `content`, `simulation`) con reintentos, rate limiting y monitoreo | `Arq`/`Celery`, `asyncio.TaskGroup` |
| `orchestrator` | Coordina quién publica, cuándo y con qué afinidades; integra compliance y storage | Grafo de afinidades, eventos de simulación |
| `simulation` | Motor de feed que emite publicaciones, comentarios, likes y reply chains reproducibles | Métricas de escenarios, reportes de auditoría |
| `compliance_guard` | Aplica reglas de seguridad, clasifica riesgos y documenta decisiones | Reglas declarativas, heurísticas locales, auditoría persistida |
| `storage` | Capa de persistencia con SQLAlchemy 2.0, migraciones Alembic, repositorios y UoW | SQLite/Postgres, registros de jobs/agents/content |
| `api` | Superficie FastAPI con endpoints equivalentes al CLI y exposición de métricas | Routers `population`, `content`, `simulation`, `jobs`, `health` |
| `cli` | Comandos Typer `azt3knet` que reproducen todos los flujos principales | Flags coherentes con la API |
| `adapters` | Stubs/mocks de feeds sociales y mensajería para conectar frontends sin tocar servicios reales | Contratos documentados |

## 🧾 Esquema de agentes sintéticos

Cada respuesta de Ollama debe entregar exactamente **N** registros únicos con el siguiente schema Pydantic:

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

- `seed` deriva determinísticamente de la especificación de población y el índice del agente.
- `interests`, `bio` y `behavioral_biases` excluyen PII y referencias a cuentas reales.
- `agent_factory` valida unicidad de `username_hint`, diversidad de género/intereses y consistencia geográfica.

## 📊 Especificación de población

Las poblaciones se definen mediante CLI o API utilizando los mismos parámetros. Ejemplo en CLI:

```bash
azt3knet populate \
  --gender female \
  --count 1000 \
  --country MX \
  --city "Mexico City" \
  --age 18-25 \
  --interests "cumbia,arte urbano" \
  --seed 20241005 \
  --preview 10
```

Equivalente en API:

```http
POST /api/populate
{
  "gender": "female",
  "count": 1000,
  "country": "MX",
  "city": "Mexico City",
  "age_range": [18, 25],
  "interests": ["cumbia", "arte urbano"],
  "seed": "20241005",
  "preview": 10
}
```

| Campo | Tipo | Requerido | Descripción |
|-------|------|-----------|-------------|
| `gender` | `female` \| `male` \| `non_binary` \| `unspecified` | Sí | Filtro de género base. |
| `count` | entero > 0 | Sí | Número de agentes a generar. |
| `country` | ISO 3166-1 alfa-2 | Sí | País de residencia simulado. |
| `city` | texto | Opcional | Ciudad específica (usa seeds compuestas). |
| `age_range` | `[min, max]` | Opcional | Ambos límites inclusive, 13 ≤ edad ≤ 90. |
| `interests` | lista de strings | Opcional | Debe contener ≥ 1 interés si se envía. |
| `seed` | string | Opcional | Determina reproducibilidad; se autogenera si falta. |
| `preview` | entero | Opcional | Muestra N registros sin persistir. |
| `persist` | bool | Opcional | Si `true`, guarda en storage y retorna `job_id`. |

Las especificaciones se transforman en prompts programáticos y precisos para Ollama, exigiendo N registros únicos que respeten el schema anterior y las políticas de compliance.

## 🔁 Flujos CLI y API

| Acción | CLI | API | Resultado |
|--------|-----|-----|-----------|
| Generar población | `azt3knet populate ...` | `POST /api/populate` | Ejecuta job en cola `population`, opcionalmente previewa y/o persiste. |
| Exportar fixtures | `azt3knet populate ... --persist --export json --path data/fixtures/mx.json` | `POST /api/populate?export=json` | Genera fixtures JSON/CSV para frontends. |
| Crear contenido | `azt3knet content draft --agent <uuid> --template street_art_campaign` | `POST /api/content/draft` | Devuelve borradores, captions, alt-text, hashtags, variaciones + metadata y `compliance_score`. |
| Correr simulación | `azt3knet sim run --scenario metro_cdmx --ticks 120` | `POST /api/simulations/{scenario}/run` | Encola job que simula feed, expone métricas y reportes. |
| Estado de jobs | `azt3knet jobs status <id>` | `GET /api/jobs/{id}` | Retorna estado (`queued`, `running`, `failed`, `completed`) y metadatos. |
| Salud/observabilidad | `azt3knet system check` | `GET /healthz`, `GET /metrics` | Healthcheck + métricas Prometheus. |

Todos los comandos aceptan `--seed` global para reproducibilidad. La API devuelve `job_id` y enlaces a exportaciones cuando aplica.

## ⚙️ Trabajo en segundo plano y observabilidad

- **Job runner/queue:** `scheduler` encapsula Arq (preferido) o Celery con Redis. Las colas separadas (`population`, `content`, `simulation`) permiten aislar cargas.
- **Logging estructurado:** JSON con campos `job_id`, `agent_id`, `seed`, `scenario`. Integración con `core.logging`.
- **Métricas Prometheus:** tiempos de generación, tasa de reintentos, tamaños de población, ratio de cumplimiento, eventos por escenario.
- **Trazas OpenTelemetry:** spans para CLI/API, workers, llamadas a Ollama y almacenamiento. Configurables vía `core.tracing`.

## 🗄️ Persistencia y migraciones

- **Storage pluggable:** SQLite para desarrollo rápido; Postgres recomendado para pruebas integradas.
- **Alembic:** migraciones viven en `infra/migrations`, ejecutables desde CLI (`azt3knet db upgrade`).
- **Repositorios y UoW:** `storage.repositories` y `storage.unit_of_work` aíslan transacciones y facilitan pruebas.
- **Exportaciones:** `agent_factory.export` produce JSON/CSV deterministas listos para frontends o análisis offline.

## 🧪 Estrategia de pruebas

- **Unitarias:** validación de schemas Pydantic, formato de prompts, seeds deterministas, reglas de compliance.
- **Integración:** pipelines end-to-end mockeando Ollama con fixtures golden y levantando Redis/Postgres vía Docker.
- **Golden tests:** snapshots de poblaciones/contenidos para semillas conocidas (`tests/golden`) garantizan estabilidad.
- **Simulación:** escenarios reproducibles verifican métricas de afinidad y actividad. Las cadenas de respuesta se comparan contra fixtures.
- **Compliance:** inyecta contenido adverso y confirma que `ComplianceGuard` bloquea, etiqueta y audita correctamente.

Ejemplo de comando de pruebas:

```bash
poetry run pytest
```

## 🧯 Políticas éticas y de cumplimiento

1. **Datos sintéticos únicamente.** Ningún agente representa personas reales y se prohíbe importar PII.
2. **Sin automatización externa.** Los adaptadores son mocks; no se conectan a APIs reales ni automatizan redes sociales.
3. **Transparencia y trazabilidad.** Cada generación registra `seed`, prompts usados, decisiones de compliance y métricas.
4. **Moderación proactiva.** Contenido riesgoso se bloquea o etiqueta y nunca se publica sin revisión explícita.
5. **Uso responsable de LLMs.** Ollama se ejecuta localmente; se documentan versiones de modelos y parámetros utilizados.

## 🔧 Puesta en marcha (resumen)

1. Instalar [Ollama](https://ollama.ai/) y descargar el modelo requerido (`ollama pull <modelo>`).
2. Configurar entorno Python (p. ej., `poetry install`).
3. Arrancar servicios auxiliares (Redis/Postgres) con `docker-compose up` dentro de `infra/docker/`.
4. Ejecutar migraciones (`azt3knet db upgrade`).
5. Levantar API (`poetry run uvicorn azt3knet.api.main:app --reload`) y worker (`poetry run azt3knet worker`).
6. Consumir CLI/API según los flujos anteriores.

## 🤝 Contribución

- Sigue las convenciones de linting y type checking (`ruff`, `mypy`).
- Agrega/actualiza pruebas, especialmente golden tests cuando cambien prompts o plantillas.
- Documenta nuevas decisiones en `docs/ADRs/`.
- Toda contribución debe mantener la premisa central: simulación local, datos sintéticos, cumplimiento estricto.

---

Azt3kNet ofrece un laboratorio seguro para experimentar con redes de agentes digitales. Gracias a seeds deterministas, observabilidad integral y cumplimiento transparente, el sistema permite iterar de forma responsable sin acercarse a la automatización de cuentas reales.
