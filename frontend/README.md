# frontend

Vecinio's web client: Vue 3 (Composition API) + Vuetify + Pinia, scaffolded
with `create-vue` and built with Vite.

## Prerequisites

- **Node.js** `^22.18.0` or `>=24.12.0` (see `engines` in `package.json`).
  Install via [nvm](https://github.com/nvm-sh/nvm) or your OS package manager.
- **npm** (bundled with Node.js).
- The **backend API** running locally, since the frontend calls it for
  everything (auth, communities, quotas, votes). From the repository root:
  ```sh
  docker compose up -d db
  uv run alembic upgrade head
  DATABASE_URL=postgresql+psycopg://vecinio:vecinio@localhost:5433/vecinio \ # pragma: allowlist secret
  JWT_SECRET_KEY=<any-dev-secret> \
    uv run uvicorn src.interfaces.api.main:app --reload
  ```
  See the root `CLAUDE.md` for details. The dev server expects the API to be
  reachable at the URL configured in `src/api/client.js`.

## Recommended IDE Setup

[VS Code](https://code.visualstudio.com/) + [Vue (Official)](https://marketplace.visualstudio.com/items?itemName=Vue.volar) (and disable Vetur).

## Recommended Browser Setup

- Chromium-based browsers (Chrome, Edge, Brave, etc.):
  - [Vue.js devtools](https://chromewebstore.google.com/detail/vuejs-devtools/nhdogjmejiglipccpnnnanhbledajbpd)
  - [Turn on Custom Object Formatter in Chrome DevTools](http://bit.ly/object-formatters)
- Firefox:
  - [Vue.js devtools](https://addons.mozilla.org/en-US/firefox/addon/vue-js-devtools/)
  - [Turn on Custom Object Formatter in Firefox DevTools](https://fxdx.dev/firefox-devtools-custom-object-formatters/)

## Customize configuration

See [Vite Configuration Reference](https://vite.dev/config/).

## Install dependencies

From the `frontend/` directory:

```sh
npm install
```

## Run the dev server

```sh
npm run dev
```

Serves the app with hot-reload at `http://localhost:5173` by default.
Requires the backend API (and its Postgres database) to be running — see
"Prerequisites" above.

## Stop the dev server

Press `Ctrl+C` in the terminal where `npm run dev` is running. If it was
started in the background, stop it with your shell's job control (`kill
%<job-id>`) or by killing the `vite` process (e.g. `pkill -f vite`).

Don't forget to also stop the local database container when you're done with
manual work, from the repository root:

```sh
docker compose down
```

## Run tests

Unit tests use Vitest + `@vue/test-utils` + jsdom:

```sh
npm run test:unit
```

## Build for production

```sh
npm run build
```

Compiles and minifies into `dist/`.

## Preview a production build

```sh
npm run preview
```

Serves the built `dist/` output locally, for a final check before deploying.

## Lint and format

```sh
npm run lint
```

Runs [oxlint](https://oxc.rs/docs/guide/usage/linter.html) and
[ESLint](https://eslint.org/) (both with `--fix`).

```sh
npm run format
```

Formats `src/` with [Prettier](https://prettier.io/).
