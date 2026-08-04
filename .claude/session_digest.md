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
  contra solo unos pocos casos de uso actuales sería adivinar, no diseñar.
  Esperar a tener más bounded contexts de negocio reales (cuotas, votaciones,
  incidencias) antes de diseñar roles finos.
- Cuando llegue el momento: probablemente un bounded context nuevo
  (`governance`), con roles como lista de asignaciones dentro de `Community`
  (parecido a `Unit.owner_ids`) porque el invariante "solo un presidente activo
  a la vez" necesita consistencia transaccional dentro del propio agregado —
  hipótesis de diseño, no decidida en firme.
- El administrador de fincas externo sustituiría (parcial o totalmente) al
  tesorero — relación exacta sin definir todavía.
- **Nuevo desde `vote`**: hoy CUALQUIER `Account` vinculada a un `Owner` que
  sea propietario de alguna `Unit` de la `Community` puede convocar una
  votación (`CreateVote`) o cerrarla (`CloseVote`) — restricción mínima
  temporal, deliberadamente laxa hasta que exista `governance`. Cuando se
  diseñe `governance`, hay que decidir si conviene restringir a un rol
  concreto (¿presidente? ¿cualquier propietario sigue pudiendo?), y también
  cómo encaja un futuro administrador de fincas externo, que probablemente
  deba poder crear/cerrar votaciones sin ser propietario de ninguna unidad.

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

### Votaciones (`vote`) — lo ya implementado y lo diferido conscientemente
El bounded context `vote` (consultas/votaciones tipo aprobar un presupuesto,
una derrama, un estudio de placas solares, etc., con voto por `Unit` —no por
persona—, ponderación por coeficiente además de por nº de unidades, y cierre
explícito con snapshot de resultados) **ya está implementado de punta a
punta**: dominio (`Vote`, `Ballot`, `VoteResult`), casos de uso (`CreateVote`,
`CastBallot`, `CloseVote`), la invariante de bloqueo de cambios de `Unit`
durante una votación abierta (mecanismo de consulta construido y probado,
aunque sin ningún caso de uso todavía que lo dispare — ver más abajo), e
infraestructura completa (Postgres, migraciones, constraint `UNIQUE` parcial
para evitar doble voto activo por unidad). Ver `CLAUDE.md` para el detalle
técnico. Lo que sigue es lo que se discutió y se decidió aplazar
deliberadamente:

- **Votaciones secretas vs públicas configurables**: de momento TODAS las
  votaciones son secretas en cuanto al contenido del voto (quién votó qué),
  aunque el padrón de participación (qué unidades ya han votado) siempre es
  público. No existe todavía un campo `is_secret`/`visibility` en `Vote` ni
  se ha diseñado qué pasaría con una votación pública — quedó explícitamente
  aplazado al principio del diseño ("no sé si ahora deberíamos abordar el
  que una votación pudiera ser secreta o no"). Si en el futuro se quiere
  soportar votaciones públicas, hace falta decidir: ¿es un campo en `Vote`
  fijado al crearla (inmutable, como `options`), y qué cambia exactamente
  a nivel de consulta (¿se puede ver el desglose de votos por unidad antes
  del cierre, o solo tras `CloseVote`?).
- **Veredicto de aprobación / mayorías LPH**: `VoteResult` reporta solo datos
  puros (recuentos y coeficientes ponderados por opción, participación) —
  nunca un `approved: bool`. La LPH exige mayorías dobles (nº de propietarios
  Y cuotas de participación) con umbrales distintos según el tipo de acuerdo
  (simple, cualificada 3/5, unanimidad). Diseñar esto requeriría un concepto
  de "tipo de decisión" con su umbral asociado — bounded context de reglas
  LPH todavía sin abrir. Por ahora, los humanos interpretan los tallies según
  el orden del día real de la junta.
- **Quién puede convocar/cerrar una votación**: ver "Roles de gobierno" más
  arriba — hoy sin restricción de rol, solo "ser propietario de alguna unit
  de la comunidad".
- **Invariante de bloqueo de `Unit` durante votación abierta — construida
  pero sin ningún caso de uso que la dispare todavía**: `VoteRepository.
  exists_open_vote_for_community(community_id)` existe y está probado (una
  `Vote` cuenta como "abierta" mientras `result is None`, sin importar si
  `end_date` ya pasó). Pero investigando el código real se confirmó que
  **ningún caso de uso actual cambia `participation_coefficient` de una
  `Unit` existente ni el conjunto de units de una `Community` ya
  persistida** — `AssignOwnerToUnit` es el único mutador de units existentes
  y solo toca `owner_ids`, no coeficientes, así que deliberadamente NO se le
  aplicó este candado. Cuando se construya un futuro caso de uso de
  subdivisión de unidades o recálculo de coeficientes, ESE es el punto donde
  hay que inyectar `VoteRepository` y crear el error de aplicación
  correspondiente (todavía sin nombre definitivo ni creado en código, para
  no dejar código muerto especulativo).
- **Interfaz HTTP (FastAPI) — ya construida**: los tres routers
  (`CreateVote`, `CastBallot`, `CloseVote`) están implementados y probados
  de punta a punta (e2e, incluyendo casos de concurrencia real y de
  precedencia entre errores). Ver `CLAUDE.md`, sección "`vote` HTTP
  interface", para el detalle técnico de las convenciones de mapeo de
  errores fijadas al construirlos — en particular, el criterio de cuándo
  unificar vs. diferenciar mensajes 404 para evitar oráculos de enumeración,
  que aplica a cualquier router futuro del proyecto, no solo a `vote`.
- **Reintento automático ante colisión de concurrencia (409/412) — sigue sin
  decidir, ahora reencuadrado como pregunta de todo el proyecto, no solo de
  `CastBallot`**: la constraint `UNIQUE` parcial en BD
  (`ix_ballots_active_per_vote_unit`) ya hace cumplir "máximo un ballot
  activo por unidad y votación", y el repositorio ya traduce la violación a
  un error de dominio (`ConcurrentBallotSubmissionError`). Pero ningún
  router del proyecto (ni `CastBallot`, ni `CloseVote`, ni ningún otro)
  captura ni reintenta ante un 409/412 de concurrencia — se devuelve tal
  cual al cliente. Al construir `CloseVote` se decidió explícitamente NO
  resolver esto de forma aislada para ese endpoint; queda anotado en el
  propio `responses={412: ...}` del router como decisión pendiente de
  diseño general. Cuando se aborde: decidir si algún router debería
  reintentar una vez automáticamente (releer el estado y responder con el
  resultado ya calculado por quien ganó la carrera, en vez de un error que
  el cliente no sabe cómo manejar), y si la respuesta es distinta según el
  endpoint (p. ej. `CastBallot` sí tiene una acción de recuperación clara
  para el cliente — reintentar el voto — mientras que un 412 en `CloseVote`
  no le da al cliente nada útil que hacer, dado que hoy la única mutación
  posible de un `Vote` es `close()`).

## Próximos pasos posibles (sin decidir orden)
- Endpoint `GET /owners/me/units` (o similar) para que un `Owner` autenticado
  vea sus viviendas — confirmado que falta (verificado en código durante el
  trabajo de `GET /auth/me`, no solo asumido): NO existe ningún método de
  repositorio para esto hoy. `Unit` vive embebido dentro del agregado
  `Community` (no es su propio agregado/tabla independiente) y
  `CommunityRepository` solo expone `save`/`get_by_id`/`exists_by_cif` — sin
  `get_by_owner_id` ni nada parecido. La única forma actual de encontrar las
  unidades de un `Owner` es cargar una `Community` conocida por id y filtrar
  `units` en cliente. Construir este endpoint requiere decidir primero CÓMO
  resolver "todas las Units de todas las Communities donde aparezca este
  owner_id" — un nuevo método de query en `CommunityRepository` que escanee
  `units` (ineficiente si crece el nº de comunidades) vs. un read model
  denormalizado — decisión de diseño abierta, no tomada todavía.
- Invariante de presidencia en `CommunityGroup` (mancomunidades) — bloqueada
  por `governance`.
- `governance` (roles) — ahora con más superficie real esperándole: la
  presidencia de mancomunidad, y quién puede convocar/cerrar votaciones.
- Coeficiente de participación por `Community` dentro de `CommunityGroup`
  (para cuotas de mancomunidad) — bloqueado hasta decidir si reutiliza
  `Unit.participation_coefficient` o es independiente.
- Caso de uso de recálculo/superseding de `Quota`.
- `billing`/`collections` (facturación y cobro de cuotas) — nuevo(s) bounded
  context(s), fuera del alcance de `quota` tal como está hoy.
- `Refund` (devoluciones a propietarios) como concepto propio.
- Caso de uso de subdivisión/alta de `Unit` con recálculo de coeficientes —
  este es también el punto donde se aplica por fin el candado de "no tocar
  units con una votación abierta" ya construido en `vote`.
- Estrategia general de reintento/manejo de errores de concurrencia
  (409/412) a nivel de router — pregunta de todo el proyecto, no solo de
  `vote`; ver nota en la sección de "Votaciones" arriba.
- Diseño de mayorías LPH por tipo de decisión, si se quiere un veredicto
  automático de aprobación en `vote` más adelante.
- Votaciones públicas (no secretas) configurables, si se retoma esa idea.
- Bounded contexts de negocio nuevos: incidencias.
- **Frontend Vue — primera parte ya construida** (Vite + Pinia + vue-router +
  Vuetify 4 + axios; ver `CLAUDE.md`, sección "Frontend", para el stack y las
  decisiones técnicas): registro, login, y alta de `Community` con sus
  `Unit`s en un único formulario. De camino se corrigieron dos huecos del
  backend que bloqueaban esto: CORS no estaba configurado en ningún sitio, y
  `ParticipationCoefficientSumError` no tenía handler registrado (devolvía
  500 en vez de 400). Pendiente, sin construir todavía: pantallas de alta de
  `Owner` y asignación a `Unit`, de `quota` y de `vote`; no hay pantalla de
  "mis comunidades" posible porque no existe ningún endpoint de listado
  (`GET /communities`), solo `GET /communities/{id}`.