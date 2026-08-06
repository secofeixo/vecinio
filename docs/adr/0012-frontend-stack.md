# ADR-0012: Frontend stack — Vite/JS (not TS), Vuetify, Pinia, localStorage tokens

## Status
Accepted, implemented. Revisit triggers noted below.

## Decisions
- **Vite**, scaffolded via `npm create vue@latest` (official `create-vue`) —
  chosen over Vuetify's own `create-vuetify` wizard for a more
  predictable/reviewable generated layout.
- **JavaScript, not TypeScript**, for now — deliberate: the developer is new
  to the Composition API, to Vuetify's component API, and to
  component-library-driven UI all at once; TS as a fourth simultaneous
  unknown was judged likely to cause tooling friction rather than
  product-logic friction. **Revisit** once the Composition API feels
  comfortable — migrating a Vite project to TS later is cheap.
- **Vuetify** (Material Design) + `@mdi/font`, via `vite-plugin-vuetify` —
  chosen over PrimeVue/Tailwind because its opinionated defaults remove most
  visual-design decisions a UX-inexperienced developer would otherwise have
  to make from scratch.
- **State**: Pinia. **Routing**: `vue-router` (via `create-vue`).
- **HTTP**: `axios`, wrapped in `src/api/client.js` — request interceptor
  attaches `Authorization: Bearer <token>` from the Pinia auth store (skipped
  for public `/auth/*` calls); response interceptor logs out + redirects to
  `/login` on any 401. No automatic refresh-and-retry-on-401 loop yet
  (deliberately deferred — needs a request queue to avoid parallel refresh
  calls; the 15-min access token TTL made this non-essential for the first
  slice, see ADR-0001).
- **Token storage**: plain `localStorage`, written through from Pinia store
  actions — not httpOnly cookies (backend returns tokens as JSON fields, not
  `Set-Cookie`; adopting cookies needs backend changes — CSRF handling,
  `SameSite`/`Secure` — not done), not memory-only Pinia state either (would
  log the user out on every page refresh). **Accepted trade-off**:
  `localStorage` is readable by any JS on the page, so an XSS hole would
  expose both the access token and the 30-day refresh token. Fine for a
  pre-production app with no real HOA member data yet — **revisit before
  that stops being true**.
- **Test infra**: Vitest + `@vue/test-utils` + `jsdom`. Scope limited to new
  work only — no retrofitted tests for `CommunityCreateView`/
  `CommunityDetailView`/`LoginView`/the auth store.
  `frontend/src/test/setup.js` stubs `window.matchMedia`/`ResizeObserver`
  (jsdom provides neither). Requires `vite.config.js`'s
  `test.server.deps.inline: ['vuetify']` — without it, mounting a
  Vuetify-wrapped component under Vitest throws
  `TypeError: Unknown file extension ".css"` (known Vitest +
  `vite-plugin-vuetify` interaction). `vite.config.js` imports
  `defineConfig` from `vitest/config`, not `vite`, to avoid a duplicate
  config file.
  `frontend/src/test/mountWithVuetify.js` and
  `frontend/src/test/testRouter.js` are the two shared test-infra pieces —
  the latter needed because a `v-btn` with `to` silently renders as a bare
  `<a>` with no `href` if no router is installed in the test, rather than
  erroring.
- No frontend CI job exists yet (`.github/workflows/ci.yml` only runs
  backend jobs) — accepted gap.

## CORS
Configured in `main.py` (`CORSMiddleware`) but hardcoded to Vite's local dev
ports (`localhost:5173`/`127.0.0.1:5173`) — **must become environment-driven
before any real deployment**.
