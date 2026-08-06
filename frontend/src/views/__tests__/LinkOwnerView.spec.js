import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { mountWithVuetify } from '@/test/mountWithVuetify'
import { createTestRouter } from '@/test/testRouter'
import LinkOwnerView from '@/views/LinkOwnerView.vue'
import { linkOwner } from '@/api/auth'

vi.mock('@/api/auth')

async function mountView() {
  const router = createTestRouter(['my-units', 'link-owner'])
  await router.push({ name: 'link-owner' })
  return { wrapper: mountWithVuetify(LinkOwnerView, { global: { plugins: [router] } }), router }
}

describe('LinkOwnerView', () => {
  beforeEach(() => {
    vi.mocked(linkOwner).mockReset()
  })

  it('disables submit until a NIF is entered', async () => {
    const { wrapper } = await mountView()

    const submit = wrapper.find('button[type="submit"]')
    expect(submit.attributes('disabled')).not.toBeUndefined()

    await wrapper.find('input').setValue('12345678Z')

    expect(submit.attributes('disabled')).toBeUndefined()
  })

  it('links the owner and redirects to my-units on success', async () => {
    vi.mocked(linkOwner).mockResolvedValue({ id: 'account-1', email: 'a@example.com' })
    const { wrapper, router } = await mountView()
    const pushSpy = vi.spyOn(router, 'push')

    await wrapper.find('input').setValue('12345678Z')
    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()

    expect(linkOwner).toHaveBeenCalledWith({ nif: '12345678Z' })
    expect(pushSpy).toHaveBeenCalledWith({ name: 'my-units' })
  })

  it('shows the API error message and stays on the page when linking fails', async () => {
    const error = new Error('Conflict')
    error.response = {
      status: 409,
      data: { detail: 'This NIF could not be linked to your account' },
    }
    vi.mocked(linkOwner).mockRejectedValue(error)
    const { wrapper } = await mountView()

    await wrapper.find('input').setValue('12345678Z')
    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()

    expect(wrapper.text()).toContain('This NIF could not be linked to your account')
  })

  it('shows a loading state on submit while the request is in flight', async () => {
    let resolvePromise
    vi.mocked(linkOwner).mockReturnValue(
      new Promise((resolve) => {
        resolvePromise = resolve
      }),
    )
    const { wrapper } = await mountView()

    await wrapper.find('input').setValue('12345678Z')
    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()

    const submit = wrapper.find('button[type="submit"]')
    expect(submit.classes()).toContain('v-btn--loading')

    resolvePromise({ id: 'account-1', email: 'a@example.com' })
    await flushPromises()
  })
})
