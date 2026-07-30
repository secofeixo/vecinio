# Vecinio — Digest de producto (para Project Knowledge de Claude.ai)

Este documento complementa a `CLAUDE.md` (que vive en el repo y es la fuente de
verdad técnica). Aquí solo van decisiones de producto o conversación que
**todavía no están implementadas en código** — cuando algo de aquí se
construya, se mueve a `CLAUDE.md` y se borra de este archivo.

## Cómo mantener esto al día
- `CLAUDE.md` se actualiza como parte normal del trabajo con Claude Code (ya lo
  llevas haciendo). Vuelve a subirlo a Project Knowledge cada vez que cierres
  un bloque de trabajo importante — no hace falta un proceso nuevo, es el
  mismo archivo.
- Este digest solo cambia cuando tomamos una decisión de producto en
  conversación que aún no se ha traducido a código. Cuando se implemente,
  bórralo de aquí.

## Decisiones de producto confirmadas, pendientes de construir

### Login individual, no compartido
Cada copropietario tiene su propia cuenta (`Account` + `Owner` + NIF propio),
no un login único por hogar — para mantener trazabilidad de quién hizo qué
acción. Ya no requiere cambios de esquema; solo asegurarse de que el flujo de
alta se use una vez por persona real.

### Mancomunidades (agrupación de comunidades — ej. "206-208")
La estructura base ya está implementada: `CommunityGroup` (bounded context
`community_group`, ver `CLAUDE.md`) — agregado independiente, referencia a
`Community` por ID, no las contiene. Pendiente de construir todavía:
- Invariante "el presidente de la mancomunidad debe ser presidente de una de
  las comunidades miembro" — no puede vivir dentro del agregado
  `CommunityGroup` solo, porque no puede consultar quién es presidente de
  otra `Community` por sí mismo; sería una comprobación de aplicación (mismo
  patrón que `AssignOwnerToUnit` verificando que el `Owner` existe). Bloqueada
  por "Roles de gobierno" (más abajo) — no existe el concepto de presidente
  todavía en ningún lado.
- Estado: base construida, invariante de presidencia sin implementar (fuera
  de alcance del trabajo hecho, deliberadamente). Prioridad: media — no
  urgente hoy.

### Roles de gobierno (presidente, tesorero, administrador de fincas externo)
- Hoy el dominio no tiene ningún concepto de rol dentro de una comunidad.
- Decisión de posponer: correcta y deliberada — diseñar la matriz de permisos
  contra solo 3-4 casos de uso actuales sería adivinar, no diseñar. Esperar a
  tener más bounded contexts de negocio reales (cuotas, incidencias) antes de
  diseñar roles finos.
- Cuando llegue el momento: probablemente un bounded context nuevo
  (`governance`), con roles como lista de asignaciones dentro de `Community`
  (parecido a `Unit.owner_ids`) porque el invariante "solo un presidente activo
  a la vez" necesita consistencia transaccional dentro del propio agregado —
  hipótesis de diseño, no decidida en firme.
- El administrador de fincas externo sustituiría (parcial o totalmente) al
  tesorero — relación exacta sin definir todavía.

## Próximos pasos posibles (sin decidir orden)
- Endpoint `GET /owners/me/units` (o similar) para que un `Owner` autenticado
  vea sus viviendas — pendiente de revisar si falta.
- Invariante de presidencia en `CommunityGroup` (mancomunidades) — bloqueada
  por `governance`.
- `governance` (roles).
- Bounded contexts de negocio nuevos: cuotas, incidencias, votaciones.
- Frontend Vue — no iniciado.
