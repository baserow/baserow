import { mountSuspended } from '@nuxt/test-utils/runtime'
import BuilderToasts from '@baserow/modules/builder/components/BuilderToasts.vue'

describe('BuilderToasts', () => {
  let store = null

  beforeEach(() => {
    store = useNuxtApp().$store
  })

  afterEach(async () => {
    for (const toast of [...store.getters['builderToast/all']]) {
      await store.dispatch('builderToast/remove', toast)
    }
  })

  const mountComponent = () =>
    mountSuspended(BuilderToasts, {
      global: { provide: { builder: { id: 1 }, mode: 'public' } },
    })

  test('renders plain toasts as-is', async () => {
    await store.dispatch('builderToast/info', {
      title: '**Saved**',
      message: 'See [details](/details)',
    })
    const wrapper = await mountComponent()

    expect(wrapper.find('.ab-toast__title strong').exists()).toBe(false)
    expect(wrapper.find('.ab-toast__title').text()).toBe('**Saved**')
    expect(wrapper.find('.ab-toast__message a').exists()).toBe(false)
    expect(wrapper.find('.ab-toast__message').text()).toBe(
      'See [details](/details)'
    )
  })

  test('renders a Markdown title inline and a Markdown message as restricted block', async () => {
    await store.dispatch('builderToast/info', {
      title: '# **Saved** [x](/x)',
      titleFormat: 'markdown',
      message:
        '# Not a heading\n\nSee [details](/details)\n\n| a |\n|---|\n| 1 |',
      messageFormat: 'markdown',
    })
    const wrapper = await mountComponent()

    const title = wrapper.find('.ab-toast__title')
    expect(title.find('.markdown--inline strong').text()).toBe('Saved')
    expect(title.find('a').exists()).toBe(false)
    expect(title.find('.ab-heading').exists()).toBe(false)

    const message = wrapper.find('.ab-toast__message')
    expect(message.find('.ab-heading').exists()).toBe(false)
    expect(message.find('table').exists()).toBe(false)
    expect(message.find('p.ab-text').exists()).toBe(true)
    expect(message.find('a.ab-link').attributes('href')).toBe('/details')
    expect(message.text()).toContain('# Not a heading')
  })
})
