// jsdom provides neither matchMedia nor ResizeObserver, both of which
// Vuetify's layout system touches internally even for basic components.
window.matchMedia =
  window.matchMedia ||
  function () {
    return {
      matches: false,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
    }
  }

window.ResizeObserver =
  window.ResizeObserver ||
  class ResizeObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
