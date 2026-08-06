# ADR-0013: "Mis viviendas" and "Vincular propietario" screens

## Status
Accepted, implemented.

## "Mis viviendas" (`MyUnitsView.vue`) — landing screen
`/` and the post-login redirect both point at `{ name: 'my-units' }` instead
of `/communities/new`. First time `App.vue`'s `v-app-bar` has real nav links
("Mis viviendas", "Nueva comunidad"), both under the existing
`v-if="auth.isAuthenticated"`.

- **Client-side grouping**: `GET /owners/me/units` (ADR-0010) returns a flat
  array with `community_name`/`community_address` repeated per unit. Grouped
  by `community_id` (first-seen order) via a standalone pure function,
  `frontend/src/utils/groupUnitsByCommunity.js` — extracted rather than
  inlined as a `computed`, specifically so grouping edge cases could be
  unit-tested without mounting Vuetify. Deliberate one-off deviation from
  the project's "inline everything" convention (ADR-0012 area) — not a
  general precedent.
- **Two distinct empty/error states, not merged**: 200 with `[]` (linked
  Owner, no Units — plain `v-alert type="info"`, no CTA) is visually and
  semantically different from 404 (`OwnerNotLinkedToAccountError`, no
  `owner_id` — same alert style plus a "Vincular propietario" `v-btn`
  linking to `{ name: 'link-owner' }`). The 404 is detected by checking
  `error.response?.status === 404` directly in the view, NOT routed through
  the shared `apiErrorMessage(error)` helper — that helper stays for
  genuinely unexpected errors; a 404 here is an expected domain state
  needing its own UI.

## "Vincular propietario" (`LinkOwnerView.vue`)
Consumes `POST /auth/me/link-owner` (ADR-0009). Reachable exclusively from
`MyUnitsView`'s 404 state — deliberately not added to the nav bar (one-time
action, only relevant to that empty state). Built against
`CommunityCreateView.vue`'s form conventions (no Vuetify `rules`, `computed
canSubmit`, top error `v-alert`, `submitting` ref driving `:loading`). On
success, redirects to `{ name: 'my-units' }`.

**`GET /auth/me` still not wired into the Pinia auth store** — considered
and skipped here too: the only entry point into this screen already only
renders for not-yet-linked accounts, so the common path never needs
pre-emptive "am I already linked" state. An already-linked account that
manually navigates to `/link-owner` gets the backend's 409 on submit instead
— accepted as a rare direct-URL rough edge.
