import { mount } from '@vue/test-utils'
import { createVuetify } from 'vuetify'

export function mountWithVuetify(component, options = {}) {
  const vuetify = createVuetify()
  return mount(component, {
    ...options,
    global: {
      ...options.global,
      plugins: [vuetify, ...(options.global?.plugins ?? [])],
    },
  })
}
