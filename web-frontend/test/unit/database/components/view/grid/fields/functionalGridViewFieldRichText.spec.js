import { TestApp } from '@baserow/test/helpers/testApp'
import FunctionalGridViewFieldRichText from '@baserow/modules/database/components/view/grid/fields/FunctionalGridViewFieldRichText'

describe('FunctionalGridViewFieldRichText component', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const mountComponent = (value) =>
    testApp.mount(FunctionalGridViewFieldRichText, {
      props: { value, workspaceId: 10 },
    })

  test('renders the Markdown preview', async () => {
    const wrapper = await mountComponent('# Title\n\n**bold** and `code`')

    expect(wrapper.find('h1').text()).toBe('Title')
    expect(wrapper.find('strong').text()).toBe('bold')
    expect(wrapper.find('code').text()).toBe('code')
  })

  test('renders links without href so unselected cells stay inert', async () => {
    const wrapper = await mountComponent('[Baserow](https://baserow.io)')

    const link = wrapper.find('a')
    expect(link.exists()).toBe(true)
    expect(link.attributes('href')).toBeUndefined()
  })

  test('truncates long values before rendering', async () => {
    const wrapper = await mountComponent('x'.repeat(500))

    const text = wrapper.text()
    expect(text.endsWith('...')).toBe(true)
    expect(text.length).toBeLessThanOrEqual(203)
  })

  test('keeps raw HTML in cell values inert', async () => {
    const wrapper = await mountComponent(
      '<script>window.hacked = true</script><img src="x" onerror="window.hacked = true">'
    )

    expect(wrapper.find('script').exists()).toBe(false)
    expect(wrapper.find('img').exists()).toBe(false)
    expect(window.hacked).toBeUndefined()
  })
})
