import { TestApp } from '@baserow/test/helpers/testApp'
import { plainTextToMarkdown } from '@baserow/modules/core/editor/richTextClipboard'
import { replaceImagesWithPlaceholder } from '@baserow/modules/core/editor/richTextImageUtils'
import FunctionalGridViewFieldRichText from '@baserow/modules/database/components/view/grid/fields/FunctionalGridViewFieldRichText'

vi.mock(
  '@baserow/modules/core/editor/richTextImageUtils',
  async (importOriginal) => {
    const actual = await importOriginal()
    return {
      ...actual,
      replaceImagesWithPlaceholder: vi.fn(actual.replaceImagesWithPlaceholder),
    }
  }
)

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

  // Sized like the names the backend creates: `<32 chars>_<sha256>.<extension>`.
  const fileName = `${'a'.repeat(32)}_${'b'.repeat(64)}.png`

  const imageRef = (urlLength, alt = 'chart') => {
    const url = 'https://s3.example.com/user_files/'.padEnd(urlLength - 4, 'x')
    return `![${alt}][${fileName}](${url}.png)`
  }

  const renderedNodes = (wrapper) =>
    [
      ...wrapper.find('.grid-field-rich-text__cell-content').element.childNodes,
    ].filter((node) => node.nodeType !== 3 || node.textContent.trim())

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

    expect(wrapper.text()).toBe(`${'x'.repeat(200)}...`)
  })

  test('puts the ellipsis of a long value inside its last paragraph', async () => {
    const wrapper = await mountComponent(
      'Lorem ipsum dolor sit amet. '.repeat(10)
    )

    const lastNode = renderedNodes(wrapper).at(-1)
    expect(lastNode.tagName).toBe('P')
    expect(lastNode.textContent.endsWith('...')).toBe(true)
  })

  test('keeps the ellipsis in the last paragraph when the cut follows a blank line', async () => {
    const wrapper = await mountComponent(
      `${'x'.repeat(198)}\n\n${'y'.repeat(50)}`
    )

    expect(wrapper.findAll('p').map((paragraph) => paragraph.text())).toEqual([
      `${'x'.repeat(198)}...`,
    ])
  })

  test('adds no ellipsis to a 200-char plain value', async () => {
    const wrapper = await mountComponent('x'.repeat(200))

    expect(wrapper.text()).toBe('x'.repeat(200))
  })

  test('adds no ellipsis when only the image references make the value long', async () => {
    const wrapper = await mountComponent(`${imageRef(250)} caption`)

    expect(wrapper.find('i.iconoir-media-image').exists()).toBe(true)
    expect(wrapper.text()).toContain('caption')
    expect(wrapper.text()).not.toContain('...')
  })

  test.each([140, 600])(
    'renders a placeholder for every image with %i-char URLs',
    async (urlLength) => {
      const ref = imageRef(urlLength)
      const wrapper = await mountComponent(`${ref} one ${ref} two ${ref} three`)

      expect(wrapper.findAll('i.iconoir-media-image')).toHaveLength(3)
      expect(wrapper.text()).toContain('three')
      expect(wrapper.text()).not.toContain('...')
    }
  )

  test('drops a placeholder the cut would split instead of showing half of it', async () => {
    const wrapper = await mountComponent(`${'x'.repeat(199)}${imageRef(140)}`)

    expect(wrapper.find('i.iconoir-media-image').exists()).toBe(false)
    expect(wrapper.text()).toBe(`${'x'.repeat(199)}...`)
  })

  test('never shows a file name or URL, wherever the cut lands', async () => {
    for (let padding = 150; padding <= 210; padding++) {
      const wrapper = await mountComponent(
        `${'x'.repeat(padding)} ${imageRef(600)} tail`
      )

      expect(wrapper.text()).not.toContain(fileName.slice(0, 8))
      expect(wrapper.text()).not.toContain('https')
    }
  })

  test('renders a multi-line alt image with a long URL as a placeholder', async () => {
    const url = 'https://s3.example.com/user_files/'.padEnd(2000, 'x')
    const wrapper = await mountComponent(
      `![line one\nline two][${fileName}](${url}) tail`
    )

    expect(wrapper.find('i.iconoir-media-image').exists()).toBe(true)
    expect(wrapper.text()).toContain('tail')
    expect(wrapper.text()).not.toContain('https://')
  })

  test('keeps the placeholders of a very long value', async () => {
    const ref = imageRef(600)
    const wrapper = await mountComponent(
      `${ref} ${ref} ${ref} ${'word '.repeat(20000)}`
    )

    expect(wrapper.findAll('i.iconoir-media-image')).toHaveLength(3)
    expect(wrapper.text().endsWith('...')).toBe(true)
    expect(wrapper.text()).not.toContain('https://')
  })

  test('processes only a bounded prefix of a very long value', async () => {
    replaceImagesWithPlaceholder.mockClear()
    await mountComponent(`(${'`a`'.repeat(33333)}`)

    const lengths = replaceImagesWithPlaceholder.mock.calls.map(
      ([content]) => content.length
    )
    expect(Math.max(...lengths)).toBeLessThanOrEqual(5000)
  })

  test('keeps raw HTML in cell values inert', async () => {
    const wrapper = await mountComponent(
      '<script>window.hacked = true</script><img src="x" onerror="window.hacked = true">'
    )

    expect(wrapper.find('script').exists()).toBe(false)
    expect(wrapper.find('img').exists()).toBe(false)
    expect(window.hacked).toBeUndefined()
  })

  test('replaces image references with a placeholder icon', async () => {
    const wrapper = await mountComponent('![photo][abc_def.png] some text')

    const text = wrapper.text()
    expect(wrapper.find('i.iconoir-media-image').exists()).toBe(true)
    expect(text).toContain('photo')
    expect(text).toContain('some text')
    expect(wrapper.find('img').exists()).toBe(false)
    expect(text).not.toContain('[abc_def.png]')
  })

  test('replaces image with URL format using placeholder', async () => {
    const wrapper = await mountComponent(
      '![chart][abc123_file456.png](https://example.com/abc123_file456.png) description'
    )

    const text = wrapper.text()
    expect(wrapper.find('i.iconoir-media-image').exists()).toBe(true)
    expect(text).toContain('chart')
    expect(text).toContain('description')
    expect(wrapper.find('img').exists()).toBe(false)
    expect(text).not.toContain('abc123_file456.png')
    expect(text).not.toContain('https://example.com')
  })

  test('never renders plain markdown images as img', async () => {
    const wrapper = await mountComponent(
      'see ![tracker](https://evil.com/pixel.png) here'
    )

    expect(wrapper.find('img').exists()).toBe(false)
    expect(wrapper.find('a').exists()).toBe(false)
    expect(wrapper.find('i.iconoir-media-image').exists()).toBe(true)
    expect(wrapper.text()).toContain('tracker')
    expect(wrapper.text()).not.toContain('evil.com')
  })
})
