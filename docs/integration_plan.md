# Plan de integración Azt3kNet + deSEC + Mailcow

## Visión general
Implementar una pipeline determinista para generar poblaciones sintéticas con identidad completa, buzón en Mailcow y DNS administrado via deSEC, accesible desde CLI y API.

## Estrategia de commits

1. **Scaffold inicial y configuración de entorno**
   - Actualizar `pyproject.toml`/dependencias necesarias (pydantic, httpx, cryptography, typer, etc.).
   - Añadir `.env.example` con nuevas variables requeridas y documentación resumida.
   - Crear estructura base en `src/azt3knet/` para módulos: `cli/`, `api/`, `services/`, `adapters/`.
   - Añadir `docker-compose.mail.yml` con Mailcow y contenedor `azt3knet-dns-bootstrap` + scripts de arranque.

2. **Bootstrap DNS y actualización dinámica**
   - Implementar `infra/dns_bootstrap.py` y `infra/dyn_updater.py` con cliente deSEC (`dns_manager.py`).
   - Añadir configuración de cron o systemd-lite en contenedor para ejecutar `dyn_updater` con intervalo.
   - Tests unitarios para `dns_manager` usando `pytest` con `responses`.

3. **Adaptador LLM y modelos canónicos**
   - Implementar `src/azt3knet/llm/adapter.py` con `generate_field` (incluye seeds deterministas).
   - Consolidar `PopulationSpec` y `AgentProfile` en `src/azt3knet/agent_factory/models.py` para evitar duplicados.
   - Mock tests para comprobar prompts y determinismo.

4. **CLI populate (modo preview)**
   - Añadir comando `azt3knet populate` en `src/azt3knet/cli/populate.py` con flags (`--gender`, `--count`, etc.).
   - Implementar `population_builder.py` que normaliza flags → `PopulationSpec` y usa LLM en preview sin persistencia.
   - Agregar documentación en `docs/cli.md` con ejemplos.

5. **Provisionamiento de buzones y persistencia**
   - Implementar `src/azt3knet/services/mailcow_provisioner.py` con llamadas POST `/api/v1/add/mailbox`, retries/backoff y manejo de conflictos.
   - Integrar cifrado de contraseñas con `SECRET_KEY_FOR_KV_ENC` (libsodium/fernet).
   - Añadir repositorio DB (`sqlalchemy`/`asyncpg` o actual stack) con tablas `agent_mailbox`, `audit_log`, etc.
   - Extender CLI/API para `--create-mailboxes` / `create_mailboxes`.
   - Tests con mocks LLM + Mailcow + DB (incluyendo rollback).

6. **API REST y script de recreación**
   - Añadir endpoint `POST /api/populate` con FastAPI (o framework actual) y seguridad admin.
   - Implementar `recreate_from_seed(population_spec, seed)` que re-sincroniza buzones y DKIM.
   - Registrar métricas/logs (audit log) y exportador seguro de credenciales.
   - Tests de integración ligeros e instrucciones en docs.

7. **Documentación y scripts finales**
   - Actualizar `README.md` con guía de despliegue.
   - Documentar flujos API/CLI, manejo de seeds y seguridad de credenciales.
   - Añadir diagramas/plantillas en `docs/` si aplica.

## Archivos iniciales a crear

- `docs/integration_plan.md` (este documento).
- `infra/dns_bootstrap.py` (esqueleto inicial con TODOs).
- `infra/dyn_updater.py` (esqueleto).
- `src/azt3knet/dns/dns_manager.py` (clase placeholder con interfaces).
- `src/azt3knet/llm/adapter.py` (función stub `generate_field`).
- `src/azt3knet/agent_factory/models.py` (dataclasses compartidas para agentes).
- `src/azt3knet/services/mailcow_provisioner.py` (interface + TODOs).
- `src/azt3knet/population/builder.py` (función stub `build_population`).
- `src/azt3knet/cli/populate.py` (CLI stub con Typer).
- `src/azt3knet/api/routes/populate.py` (FastAPI router stub).
- `tests/test_population_preview.py` (test placeholder que marca TODO para mocks).
- `tests/conftest.py` (fixtures básicos para futuras pruebas).

Cada archivo inicial incluirá docstrings y `TODO` indicando la funcionalidad por implementar en fases posteriores.

