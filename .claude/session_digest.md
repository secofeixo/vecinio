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
- **Coeficiente de participación de cada `Community` dentro de una
  `CommunityGroup`** (para poder calcular cuotas de mancomunidad, no solo de
  comunidad individual) — decisión explícitamente aplazada durante el diseño
  del bounded context `quota`. No se sabe todavía si el reparto interno de un
  gasto de mancomunidad dentro de cada comunidad reutilizará
  `Unit.participation_coefficient` (el ya existente para gastos propios) o si
  necesitará un coeficiente independiente — esa ambigüedad es precisamente lo
  que bloquea diseñar esto ahora. Cuando se retome, ya hay adelantadas tres
  sub-decisiones (ver "Cuotas de mancomunidad" más abajo).
- No hay invariante de exclusividad/presidencia entre distintas mancomunidades
  — deliberadamente fuera de alcance, ver "Roles de gobierno".

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

### Cuotas (`quota`) — lo ya implementado y lo diferido conscientemente
El bounded context `quota` (creación de una `Quota`: reparto de un importe
entre las `Unit` de una `Community` en un momento dado, con snapshot
inmutable de coeficientes, largest-remainder method para el redondeo, y
validación de no-solapamiento entre cuotas `ordinary`) **ya está
implementado** — ver `CLAUDE.md` para el detalle técnico y los invariantes
cerrados. Lo que sigue es lo que se discutió y se decidió aplazar
deliberadamente, para no perderlo de vista:

- **Facturación / cobro**: el alcance actual es allocation puro (reparto de
  X euros entre unidades). No hay emisión de recibos, registro de pagos,
  impagos ni intereses de demora — es un bounded context (o varios:
  `billing`, `collections`) todavía por diseñar.
- **Modo de cobro / periodicidad de pago** (mensual, trimestral, semestral,
  pago único): explícitamente fuera de este incremento — depende del futuro
  bounded context de facturación. `Quota` sí tiene `period_start`/
  `period_end` (el periodo que cubre el presupuesto), que es un concepto
  distinto y ya implementado.
- **`ordinary` vs `extraordinary`**: hoy es solo una etiqueta, sin reglas de
  negocio diferenciadas (ambas se validan igual salvo por la comprobación de
  solapamiento, que solo aplica entre `ordinary`↔`ordinary`). Pendiente:
  definir si en el futuro deben tener invariantes distintos (p. ej. exigir
  la línea de fondo de reserva solo en `ordinary`).
- **Recálculo / superseding**: el campo `supersedes_quota_id` existe en el
  modelo, pero no hay ningún caso de uso que lo dispare todavía. Decisión ya
  tomada para cuando se construya: una `Quota` nunca se muta in-place (es
  inmutable); un recálculo crea una `Quota` **nueva** que referencia a la
  anterior vía `supersedes_quota_id`. Si el coeficiente de alguna `Unit`
  cambia después de creada una `Quota` (p. ej. una unidad se subdivide), las
  cuotas ya calculadas quedan congeladas con el coeficiente vigente en su
  momento — no se recalculan automáticamente; el recálculo es un proceso
  explícito, todavía sin construir.
- **Catálogo cerrado de conceptos** (`ConceptType`): hoy `QuotaLine.concept`
  es texto libre, sin catálogo reutilizable. Aplazado deliberadamente —
  limita el análisis futuro tipo "gasto en limpieza este año vs el anterior"
  a que el texto coincida exactamente, pero se acepta como limitación
  conocida por ahora.
- **`Refund` / devoluciones a propietarios**: `Quota.total` está forzado a
  ser estrictamente positivo (`> 0`); una devolución real de dinero a los
  propietarios (p. ej. una subvención mayor que el gasto) necesitaría su
  propio concepto explícito, todavía no diseñado — no se modela invirtiendo
  el signo de una `Quota`.
- **Fondo de reserva** (obligatorio por LPH art. 9.1.f, mínimo 10% del
  presupuesto ordinario anual): se modela hoy como una línea de concepto más
  dentro de `QuotaLine` (texto libre, sin campo estructural dedicado ni
  cálculo automático del mínimo legal). Si en el futuro se quiere validar
  que ese mínimo se cumple, hace falta revisar este punto.
- **Cuotas de mancomunidad**: bloqueado por el punto de coeficiente de
  `CommunityGroup` (ver arriba). Ya adelantado, para cuando se retome:
  (1) si se implementa, el coeficiente de participación de cada `Community`
  en la mancomunidad será un **valor manual, fijado explícitamente** (no
  calculado automáticamente a partir de nº de unidades o superficie);
  (2) sí debe poder cambiar el conjunto de miembros de una mancomunidad ya
  creada (añadir/quitar), con el reparto recalculándose también de forma
  manual, no automática; (3) no se ha decidido si conviene en el futuro
  poder elegir entre cálculo manual o automático — eso queda para más
  adelante, sin diseñar todavía.

## Próximos pasos posibles (sin decidir orden)
- Endpoint `GET /owners/me/units` (o similar) para que un `Owner` autenticado
  vea sus viviendas — pendiente de revisar si falta.
- Invariante de presidencia en `CommunityGroup` (mancomunidades) — bloqueada
  por `governance`.
- `governance` (roles).
- Coeficiente de participación por `Community` dentro de `CommunityGroup`
  (para cuotas de mancomunidad) — bloqueado hasta decidir si reutiliza
  `Unit.participation_coefficient` o es independiente.
- Caso de uso de recálculo/superseding de `Quota`.
- `billing`/`collections` (facturación y cobro de cuotas) — nuevo(s) bounded
  context(s), fuera del alcance de `quota` tal como está hoy.
- `Refund` (devoluciones a propietarios) como concepto propio.
- Bounded contexts de negocio nuevos: incidencias, votaciones.
- Frontend Vue — no iniciado.