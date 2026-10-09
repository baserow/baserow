import { TestApp } from '@baserow/test/helpers/testApp'
import BuilderToasts from '@baserow/modules/builder/components/BuilderToasts.vue'

describe('BuilderToasts', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const mountWithToast = async (toast) => {
    await testApp.store.dispatch('builderToast/info', toast)
    return testApp.mount(BuilderToasts)
  }

  test('renders a plain title and message without interpreting markdown', async () => {
    const wrapper = await mountWithToast({
      title: '**Saved**',
      message: 'Line 1\nLine 2',
    })

    const title = wrapper.find('.ab-toast__title')
    expect(title.text()).toBe('**Saved**')
    expect(title.find('strong').exists()).toBe(false)
    expect(
      wrapper.findAll('.ab-toast__message p.ab-text').map((p) => p.text())
    ).toEqual(['Line 1', 'Line 2'])
  })

  test('renders a markdown title inline and a markdown message as a block', async () => {
    const wrapper = await mountWithToast({
      title: '**Saved**',
      titleFormat: 'markdown',
      message: 'Row _created_\n\n[Open it](https://baserow.io)',
      messageFormat: 'markdown',
    })

    const title = wrapper.find('.ab-toast__title')
    expect(title.find('strong').text()).toBe('Saved')
    expect(title.find('p').exists()).toBe(false)

    const message = wrapper.find('.ab-toast__message')
    expect(message.findAll('p.ab-text')).toHaveLength(2)
    expect(message.find('em').text()).toBe('created')
    expect(message.find('a.ab-link').attributes('href')).toBe(
      'https://baserow.io'
    )
  })
})
