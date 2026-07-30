# Vecinio

Backend para la gestión de comunidades de propietarios (Homeowners
Association Management): comunidades, unidades/pisos, propietarios,
cuentas de acceso, agrupaciones de comunidades (mancomunidades) y cuotas.

Construido con **Tactical DDD** (sin CQRS ni Event Sourcing, decisión
deliberada) sobre **FastAPI** async y **PostgreSQL**.

## Stack técnico

- **Backend**: Python 3.12+, FastAPI, SQLAlchemy async (driver `psycopg`,
  único driver de Postgres del proyecto).
- **Gestor de paquetes**: [`uv`](https://docs.astral.sh/uv/) (no `poetry`,
  no `pip` directo).
- **Persistencia**: PostgreSQL, migraciones con **Alembic**
  (`migrations/`, única fuente de verdad del esquema).
- **Auth**: JWT de acceso (vida corta) + refresh tokens opacos
  (revocables, hasheados en BD). Hash de contraseñas con `pwdlib`
  (argon2id).
- **Frontend**: Vue 3 + Pinia — todavía no iniciado.

## Puesta en marcha

### Requisitos

- Python 3.12+
- [`uv`](https://docs.astral.sh/uv/getting-started/installation/)
- Docker (para tests de integración/e2e vía testcontainers, y opcionalmente
  para levantar Postgres en local)
- PostgreSQL accesible (local, Docker o remoto) para ejecutar la API

### Instalar dependencias

```bash
uv sync
```

### Variables de entorno

La API requiere:

- `DATABASE_URL` — cadena de conexión a PostgreSQL (driver `psycopg`,
  p. ej. `postgresql+psycopg://user:pass@localhost:5432/vecinio`)   # pragma: allowlist secret
- `JWT_SECRET_KEY` — clave secreta para firmar los JWT

### Aplicar migraciones

```bash
uv run alembic upgrade head
```

### Levantar la API en local

```bash
DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/vecinio \   # pragma: allowlist secret
JWT_SECRET_KEY=change-me \
uv run uvicorn src.interfaces.api.main:app --reload
```

## Tests

El proyecto distingue tres niveles de test:

| Nivel | Comando | Requiere Docker |
|---|---|---|
| Unitarios (sin I/O) | `uv run pytest tests/unit` | No |
| Integración (Postgres real vía testcontainers + Alembic) | `uv run pytest tests/integration` | Sí |
| E2E (`httpx.AsyncClient` contra la app FastAPI completa) | `uv run pytest tests/e2e` | Sí |
| Suite completa | `uv run pytest tests` | Sí |

Los tests de integración y e2e provisionan el esquema ejecutando
`alembic upgrade head` / `downgrade base` contra un contenedor Postgres real
(nunca `Base.metadata.create_all`), para que el esquema probado sea siempre
el que generan las migraciones.

## Calidad de código / pre-commit

```bash
uv run pre-commit run --all-files
```

Incluye, entre otros: `black`, `isort`, `flake8` (+`flake8-bugbear`),
`mypy`, `pydocstyle` (convención Google), `complexipy` (complejidad máxima
12) y `detect-secrets`. Los commits deben seguir
[Conventional Commits](https://www.conventionalcommits.org/) (verificado
con `commitizen`).

`migrations/` está excluido de todos estos hooks (`exclude: ^migrations/`
en `.pre-commit-config.yaml`) — es una brecha conocida y aceptada, no
pendiente de revisión inmediata.

## CI

GitHub Actions (`.github/workflows/ci.yml`) ejecuta dos jobs en paralelo,
cada uno con timeout de 15 minutos:

- `lint`: `pre-commit run --all-files`
- `test`: `pytest tests/unit tests/integration tests/e2e` (requiere Docker)

## Convenciones de nombres y estilo

- **Idioma**: todo el código (aggregates, entidades, value objects, casos
  de uso, variables, comentarios) está en inglés. Únicas excepciones: `CIF`
  y `NIF`/`NIE` (identificadores legales españoles sin equivalente en
  inglés), que conservan su nombre original.
- **IDs de dominio**: value objects tipados (`CommunityId`, `OwnerId`,
  `AccountId`, etc.), nunca un `str`/`UUID` a secas cruzando capas —
  excepto en el límite `execute()` de la capa de aplicación, que recibe
  primitivos (str, UUID, Decimal) y construye los value objects
  internamente.
- **Casos de uso**: una clase por caso de uso, con un único método
  `execute()`. No se fusionan dos casos de uso en un mismo handler. Las
  excepciones de dominio se propagan sin capturarse/envolverse en la capa
  de aplicación.
- **Repositorios**: interfaces (`ABC`) en `domain/`, implementación en
  `infrastructure/`. Todos los métodos son `async def`.
- **Inmutabilidad**: value objects/entidades/aggregates son modelos
  pydantic `frozen=True` por defecto; los aggregate roots que mutan usan
  `validate_assignment=True` en su lugar.
- **Validación de invariantes**: siempre en métodos del aggregate, nunca en
  el router de FastAPI ni en el caso de uso. Las comprobaciones de
  existencia entre agregados (p. ej. "¿existe este Owner?") viven en el
  caso de uso, nunca dentro del propio aggregate.
- **Estructura por bounded context**: cada contexto (`community`, `owner`,
  `identity`, `community_group`, `quota`, …) tiene su propia carpeta
  reflejada en `domain/`, `application/` e `infrastructure/`.

Para las decisiones de arquitectura y los invariantes de negocio ya
cerrados (concurrencia optimista, manejo de `IntegrityError`, reglas de
cada bounded context, etc.), ver [`CLAUDE.md`](CLAUDE.md).
