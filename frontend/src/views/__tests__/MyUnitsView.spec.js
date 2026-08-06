import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { mountWithVuetify } from '@/test/mountWithVuetify'
import { createTestRouter } from '@/test/testRouter'
import MyUnitsView from '@/views/MyUnitsView.vue'
import { getMyUnits } from '@/api/owners'

vi.mock('@/api/owners')

const address = {
  street: 'Calle Uno',
  number: '1',
  city: 'Vigo',
  postal_code: '36201',
  province: 'Pontevedra',
}

describe('MyUnitsView', () => {
  beforeEach(() => {
    vi.mocked(getMyUnits).mockReset()
  })

  it('shows a loading indicator while the request is in flight', async () => {
    let resolvePromise
    vi.mocked(getMyUnits).mockReturnValue(
      new Promise((resolve) => {
        resolvePromise = resolve
      }),
    )

    const wrapper = mountWithVuetify(MyUnitsView)

    expect(wrapper.find('.v-progress-circular').exists()).toBe(true)

    resolvePromise([])
    await flushPromises()
  })

  it('renders units grouped by community on success', async () => {
    vi.mocked(getMyUnits).mockResolvedValue([
      {
        id: 'unit-1',
        identifier: '1A',
        participation_coefficient: '0.6',
        community_id: 'community-1',
        community_name: 'Comunidad Uno',
        community_address: address,
      },
      {
        id: 'unit-2',
        identifier: '2C',
        participation_coefficient: '1',
        community_id: 'community-2',
        community_name: 'Comunidad Dos',
        community_address: { ...address, street: 'Calle Dos', number: '2' },
      },
    ])

    const wrapper = mountWithVuetify(MyUnitsView)
    await flushPromises()

    const text = wrapper.text()
    expect(text).toContain('Comunidad Uno')
    expect(text).toContain('Comunidad Dos')
    expect(text).toContain('1A')
    expect(text).toContain('60%')
    expect(text).toContain('2C')
    expect(text).toContain('100%')
  })

  it('shows a distinct empty state when the owner has zero units, with no CTA', async () => {
    vi.mocked(getMyUnits).mockResolvedValue([])

    const wrapper = mountWithVuetify(MyUnitsView)
    await flushPromises()

    expect(wrapper.text()).toContain('Aún no tienes viviendas asociadas a tu cuenta.')
    expect(wrapper.find('button').exists()).toBe(false)
  })

  it('shows a dedicated message and a CTA linking to /link-owner when the account has no linked owner (404)', async () => {
    const error = new Error('Not Found')
    error.response = { status: 404, data: { detail: 'No owner is linked to this account' } }
    vi.mocked(getMyUnits).mockRejectedValue(error)
    const router = createTestRouter(['my-units', 'link-owner'])

    const wrapper = mountWithVuetify(MyUnitsView, { global: { plugins: [router] } })
    await flushPromises()

    expect(wrapper.text()).toContain('Tu cuenta no tiene ningún propietario vinculado todavía.')
    const cta = wrapper.find('.v-btn')
    expect(cta.exists()).toBe(true)
    expect(cta.classes()).not.toContain('v-btn--disabled')
    expect(cta.attributes('href')).toBe('/link-owner')
  })

  it('shows a generic error message for a non-404 failure', async () => {
    vi.mocked(getMyUnits).mockRejectedValue(new Error('Network Error'))

    const wrapper = mountWithVuetify(MyUnitsView)
    await flushPromises()

    expect(wrapper.text()).toContain('Unexpected error')
  })
})
