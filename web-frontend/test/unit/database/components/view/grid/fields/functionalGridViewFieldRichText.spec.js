import { TestApp } from '@baserow/test/helpers/testApp'
import { plainTextToMarkdown } from '@baserow/modules/core/editor/richTextClipboard'
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

  test('renders every repeated blank line pasted from plain text', async () => {
    const wrapper = await mountComponent(
      plainTextToMarkdown('ciao\n\n\n\nmiao')
    )

    expect(wrapper.findAll('p').map((paragraph) => paragraph.text())).toEqual([
      'ciao',
      '',
      '',
      '',
      'miao',
    ])
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
    expect(text.length).toBeLessThanOrEqual(504)
  })

  test('keeps raw HTML in cell values inert', async () => {
    const wrapper = await mountComponent(
      '<script>window.hacked = true</script><img src="x" onerror="window.hacked = true">'
    )

    expect(wrapper.find('script').exists()).toBe(false)
    expect(wrapper.find('img').exists()).toBe(false)
    expect(window.hacked).toBeUndefined()
  })

  test('replaces image references with placeholder emoji', async () => {
    const wrapper = await mountComponent('![photo][abc_def.png] some text')

    const text = wrapper.text()
    expect(text).toContain('🖼 photo')
    expect(text).toContain('some text')
    expect(wrapper.find('img').exists()).toBe(false)
    expect(text).not.toContain('[abc_def.png]')
  })

  test('replaces image with URL format using placeholder', async () => {
    const wrapper = await mountComponent(
      '![chart][abc123_file456.png](https://example.com/abc123_file456.png) description'
    )

    const text = wrapper.text()
    expect(text).toContain('🖼 chart')
    expect(text).toContain('description')
    expect(wrapper.find('img').exists()).toBe(false)
    expect(text).not.toContain('abc123_file456.png')
    expect(text).not.toContain('https://example.com')
  })
})
