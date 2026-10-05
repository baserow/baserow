import { TestApp } from '@baserow/test/helpers/testApp'
import RowCardFieldRichText from '@baserow/modules/database/components/card/RowCardFieldRichText'

describe('RowCardFieldRichText component', () => {
  let testApp = null
  let store = null

  beforeEach(() => {
    testApp = new TestApp()
    store = testApp.store
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const mountComponent = (value, props = {}) =>
    testApp.mount(RowCardFieldRichText, {
      props: { value, workspaceId: 10, ...props },
    })

  test('renders the Markdown preview', async () => {
    const wrapper = await mountComponent('## Card title\n\n- item')

    expect(wrapper.find('h2').text()).toBe('Card title')
    expect(wrapper.find('ul li').text()).toBe('item')
  })

  test('renders clickable links opening a new tab', async () => {
    const wrapper = await mountComponent('[Baserow](https://baserow.io)')

    const link = wrapper.find('a')
    expect(link.attributes('href')).toBe('https://baserow.io')
    expect(link.attributes('target')).toBe('_blank')
    expect(link.attributes('rel')).toBe('noopener noreferrer nofollow')
  })

  test('resolves mentions against the workspace users', async () => {
    await store.dispatch('workspace/forceCreate', {
      id: 10,
      name: 'Workspace',
      users: [{ user_id: 5, name: 'Jane Doe' }],
    })
    const wrapper = await mountComponent('ping @5 and @99')

    const mentions = wrapper.findAll('.rich-text-editor__mention')
    expect(mentions).toHaveLength(1)
    expect(mentions[0].text()).toBe('@Jane Doe')
    expect(mentions[0].attributes('data-id')).toBe('5')
    expect(wrapper.text()).toContain('and @99')
  })

  test('keeps mentions as text when mentions are disabled', async () => {
    await store.dispatch('workspace/forceCreate', {
      id: 10,
      name: 'Workspace',
      users: [{ user_id: 5, name: 'Jane Doe' }],
    })
    const wrapper = await mountComponent('ping @5', { enableMentions: false })

    expect(wrapper.find('.rich-text-editor__mention').exists()).toBe(false)
    expect(wrapper.text()).toBe('ping @5')
  })

  test.each([true, false])(
    'renders an image only when enableImages is %s',
    async (enableImages) => {
      const wrapper = await mountComponent(
        '![a][abc123_def456.png](https://example.com/a.png)',
        { enableImages }
      )

      expect(wrapper.find('img').exists()).toBe(enableImages)
    }
  )

  test('keeps raw HTML in cell values inert', async () => {
    const wrapper = await mountComponent(
      '<script>window.hacked = true</script><img src="x" onerror="window.hacked = true">'
    )

    expect(wrapper.find('script').exists()).toBe(false)
    expect(wrapper.find('img').exists()).toBe(false)
    expect(window.hacked).toBeUndefined()
  })
})
