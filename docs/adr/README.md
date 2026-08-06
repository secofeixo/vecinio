# ADRs — Vecinio

Decisiones ya cerradas, con su razonamiento completo, extraídas de
`CLAUDE.md` para mantenerlo ligero. `CLAUDE.md` enlaza aquí cuando hace falta
el "por qué"; estos ficheros NO se cargan en cada sesión de Claude Code —
solo se leen cuando alguien (humano o Claude) necesita el contexto histórico
de una decisión concreta.

| ADR | Tema |
|---|---|
| [0001](0001-auth-stack.md) | Auth: JWT + refresh opaco, pwdlib/argon2id |
| [0002](0002-testing-strategy.md) | Tests con Alembic real, no `metadata.create_all` |
| [0003](0003-ddd-no-cqrs-no-event-sourcing.md) | DDD táctico sin CQRS/Event Sourcing |
| [0004](0004-vote-http-error-conventions.md) | Convenciones HTTP de `vote`: no-enumeración |
| [0005](0005-check-order-precedence.md) | Orden de comprobación como contrato testeado |
| [0006](0006-ballot-aggregate-and-partial-index.md) | `Ballot` como agregado + índice único parcial |
| [0007](0007-vote-jsonb-persistence.md) | `Vote`/`Ballot` en JSONB + bug `none_as_null` |
| [0008](0008-auth-me-endpoint.md) | `GET /auth/me` |
| [0009](0009-link-owner-nif-self-service.md) | `POST /auth/me/link-owner`: autoservicio por NIF |
| [0010](0010-owners-me-units-endpoint.md) | `GET /owners/me/units` |
| [0011](0011-quota-overlap-and-concurrency-strategy.md) | Solapamiento de `Quota` + estrategia de reintento (abierta) |
| [0012](0012-frontend-stack.md) | Stack frontend: Vite/JS, Vuetify, Pinia, localStorage |
| [0013](0013-frontend-screens-my-units-link-owner.md) | Pantallas "Mis viviendas" / "Vincular propietario" |

## Cómo añadir un ADR nuevo
Cuando una sesión de trabajo cierre una decisión con justificación no
trivial (por qué se eligió X sobre Y, un bug encontrado y su fix, un
trade-off aceptado con condición de revisión), créalo aquí con el siguiente
número correlativo. En `CLAUDE.md` deja solo la regla resultante en una
línea + link al ADR. No dupliques el razonamiento completo en los dos sitios.
