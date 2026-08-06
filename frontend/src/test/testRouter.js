import { createMemoryHistory, createRouter } from 'vue-router'

// Minimal router for components that use useRouter()/RouterLink (router.push,
// `:to` bindings) in isolation, without pulling in the app's real router
// (which requires Pinia/auth guards already installed). Routes are stubbed
// with trivial components -- tests only assert on navigation, never on the
// stub's own rendered content.
export function createTestRouter(routeNames) {
  return createRouter({
    history: createMemoryHistory(),
    routes: routeNames.map((name) => ({
      path: `/${name}`,
      name,
      component: { template: '<div />' },
    })),
  })
}
