import { mountSuspended } from '@nuxt/test-utils/runtime'
import { reactive, nextTick } from 'vue'
import { enableAutoUnmount } from '@vue/test-utils'
import HTMLElement from '@baserow_enterprise/builder/components/elements/HTMLElement'
import { isAuthorCodeRestricted } from '@baserow/modules/builder/utils/authorCode'

enableAutoUnmount(afterEach)

const EDITOR_URL = 'https://editor.example.com'

// Whether the page is served on an editor hostname. Applications get their
// own hostname unless a test shares the editor's.
let isWebFrontendHostname

// Preview gets its own hostname unless a test shares the editor's.
function setPreviewUrl(url, relaxed = false) {
  const config = useRuntimeConfig().public
  config.publicWebFrontendUrl = EDITOR_URL
  config.builderPreviewUrl = url
  config.builderDangerousRelaxPreviewSecurity = relaxed
}

beforeEach(() => {
  isWebFrontendHostname = false
  setPreviewUrl('https://preview.example.com')
})

const snippet =
  '<section id="anchor" class="widget" data-lang="en" aria-label="Demo">Widget</section>'

function mountElement(
  mode,
  contextMode = mode,
  html = { formula: JSON.stringify(snippet) },
  untrusted = false,
  context = {}
) {
  if (contextMode === 'editing') isWebFrontendHostname = true
  return mountSuspended(HTMLElement, {
    props: {
      element: {
        type: 'html',
        html:
          typeof html === 'string' ? { formula: JSON.stringify(html) } : html,
      },
    },
    global: {
      mocks: {
        $isAuthorCodeRestricted: () =>
          isAuthorCodeRestricted({
            isWebFrontendHostname,
            publicConfig: useRuntimeConfig().public,
          }),
      },
      provide: {
        mode,
        builder: { untrusted_content: untrusted },
        applicationContext: { mode: contextMode, ...context },
      },
    },
  })
}

// innerHTML leaves a script inert; running one means creating a fresh copy.
async function mountCountingScripts(...args) {
  const createElement = vi.spyOn(document, 'createElement')
  const wrapper = await mountElement(...args)
  const created = createElement.mock.results.filter(
    ({ value }) => value?.tagName === 'SCRIPT'
  ).length
  createElement.mockRestore()
  return { wrapper, created }
}

const scriptSnippet = '<div id="anchor"></div><script>window.x = 1</script>'

describe('HTML element', () => {
  test.each(['editing', 'public'])(
    'isolates editor HTML in a script-disabled iframe with local mode %s',
    async (mode) => {
      const wrapper = await mountElement(mode, 'editing')
      const frame = wrapper.get('iframe')
      expect(frame.attributes('srcdoc')).toBe(snippet)
      expect(frame.attributes('sandbox')).toBe('allow-same-origin')
      expect(frame.attributes('tabindex')).toBe('-1')
      expect(frame.classes()).not.toContain(
        'html-element__preview--interactive'
      )
      const hint = wrapper.get(
        'button[aria-label="iframeElementForm.editorEmbedHint"]'
      )
      await hint.trigger('focus')
      expect(document.querySelector('.tooltip').textContent).toBe(
        'iframeElementForm.editorEmbedHint'
      )
      await hint.trigger('keydown', { key: 'Escape' })
      expect(document.querySelector('.tooltip')).toBeNull()
      expect(wrapper.find('#anchor').exists()).toBe(false)
    }
  )
  test.each(['preview', 'public'])(
    'inserts the original widget in %s',
    async (mode) => {
      const wrapper = await mountElement(mode)
      expect(wrapper.get('#anchor').attributes()).toMatchObject({
        class: 'widget',
        'data-lang': 'en',
        'aria-label': 'Demo',
      })
      expect(wrapper.find('iframe').exists()).toBe(false)
      expect(
        wrapper
          .find('[aria-label="iframeElementForm.editorEmbedHint"]')
          .exists()
      ).toBe(false)
    }
  )
  test.each([
    ['  ', false],
    [snippet, true],
  ])('omits the hint for empty or untrusted HTML', async (html, untrusted) => {
    const wrapper = await mountElement('editing', 'editing', html, untrusted)
    expect(wrapper.text()).toContain(
      untrusted
        ? 'iframeElementForm.untrustedContent'
        : 'htmlElement.placeholder'
    )
    expect(wrapper.find('iframe').exists()).toBe(false)
    expect(wrapper.find('button').exists()).toBe(false)
  })

  test('preserves form controls and relative links with spaces', async () => {
    const html =
      '<form><input name="localName"><input name="attributes"></form><a href="java script:docs">Docs</a>'
    const wrapper = await mountElement('public', 'public', html)
    expect(
      wrapper.findAll('input').map((input) => input.attributes('name'))
    ).toEqual(['localName', 'attributes'])
    expect(wrapper.get('a').attributes('href')).toBe('java script:docs')
  })

  test('preserves trusted HTML without filtering its attributes or scripts', async () => {
    const html =
      '<button id="anchor" onclick="this.textContent=123">Click</button><script src="/widget.js"></script>'
    const wrapper = await mountElement('preview', 'preview', html)
    expect(wrapper.get('#anchor').attributes('onclick')).toBe(
      'this.textContent=123'
    )
    expect(wrapper.get('script').attributes('src')).toBe('/widget.js')
  })

  test.each(['preview', 'public'])(
    'activates inline scripts in %s',
    async (mode) => {
      const html = '<div id="anchor"></div><script>window.render = 1</script>'
      const createElement = vi.spyOn(document, 'createElement')
      const wrapper = await mountElement(mode, mode, html)
      // innerHTML leaves a script inert; the element swaps in a fresh copy.
      const fresh = createElement.mock.results.find(
        ({ value }) => value?.tagName === 'SCRIPT'
      )?.value
      createElement.mockRestore()
      expect(wrapper.get('script').element).toBe(fresh)
      expect(fresh.parentElement.innerHTML).toBe(html)
    }
  )

  test('does not run scripts in the editor', async () => {
    const html = '<script>window.render = 1</script>'
    const wrapper = await mountElement('editing', 'editing', html)
    expect(wrapper.find('script').exists()).toBe(false)
    expect(wrapper.get('iframe').attributes('sandbox')).toBe(
      'allow-same-origin'
    )
  })

  test('uses the hostname restriction without requiring an explicit visitor mode', async () => {
    const wrapper = await mountElement('public', '')
    expect(wrapper.find('#anchor').exists()).toBe(true)
  })

  test.each([
    ['', false],
    [snippet, true],
  ])('withholds empty or untrusted content', async (html, untrusted) => {
    const wrapper = await mountElement('preview', 'preview', html, untrusted)
    expect(wrapper.find('#anchor').exists()).toBe(false)
    expect(wrapper.text()).toBe('')
  })
})

test.each(['editing', 'preview', 'public'])(
  'updates resolved HTML when page data changes in %s',
  async (mode) => {
    const page = reactive({ parameters: { name: 'First' } })
    const wrapper = await mountElement(
      mode,
      mode,
      {
        formula: `concat('<p id="dynamic">', get('page_parameter.name'), '</p>')`,
        mode: 'advanced',
      },
      false,
      { page }
    )
    const rendered = () =>
      mode === 'editing'
        ? wrapper.get('iframe').attributes('srcdoc')
        : wrapper.get('#dynamic').text()
    expect(rendered()).toContain('First')
    await useNuxtApp().$store.dispatch('pageParameter/setParameter', {
      page,
      name: 'name',
      value: 'Second',
    })
    await nextTick()
    expect(rendered()).toContain('Second')
  }
)

test.each([{ formula: "''" }, { formula: 'concat(' }])(
  'shows an empty editor placeholder when the formula has no result',
  async (html) => {
    const wrapper = await mountElement('editing', 'editing', html)
    expect(wrapper.find('iframe').exists()).toBe(false)
    expect(wrapper.text()).toContain('htmlElement.placeholder')
  }
)

describe('HTML element on the editor hostname', () => {
  beforeEach(() => {
    isWebFrontendHostname = true
    setPreviewUrl(`${EDITOR_URL}:3001`)
  })

  test.each(['preview', 'public'])(
    'shows the HTML without running it and without the editor hint in %s',
    async (mode) => {
      const wrapper = await mountElement(mode)

      const frame = wrapper.get('iframe')
      expect(frame.attributes('srcdoc')).toBe(snippet)
      expect(frame.attributes('sandbox')).toBe('allow-same-origin')
      expect(frame.attributes('tabindex')).toBeUndefined()
      expect(frame.classes()).toContain('html-element__preview--interactive')
      expect(wrapper.find('#anchor').exists()).toBe(false)
      expect(wrapper.find('.html-element__hint').exists()).toBe(false)
    }
  )

  test.each(['editing', 'preview', 'public'])(
    'inserts the widget in %s when the instance relaxes security',
    async (mode) => {
      setPreviewUrl(`${EDITOR_URL}:3001`, true)
      const wrapper = await mountElement(mode)

      expect(wrapper.find('iframe').exists()).toBe(false)
      expect(wrapper.get('#anchor').text()).toBe('Widget')
      expect(wrapper.find('.html-element__hint').exists()).toBe(false)
    }
  )

  test.each(['preview', 'public'])(
    'keeps scripts in the frame and activates none in %s',
    async (mode) => {
      const { wrapper, created } = await mountCountingScripts(
        mode,
        mode,
        scriptSnippet
      )

      const frame = wrapper.get('iframe')
      expect(frame.attributes('srcdoc')).toBe(scriptSnippet)
      expect(frame.attributes('sandbox')).toBe('allow-same-origin')
      expect(wrapper.find('script').exists()).toBe(false)
      expect(created).toBe(0)
    }
  )

  test.each(['editing', 'preview', 'public'])(
    'activates scripts in %s when the instance relaxes security',
    async (mode) => {
      setPreviewUrl(`${EDITOR_URL}:3001`, true)
      const { wrapper, created } = await mountCountingScripts(
        mode,
        mode,
        scriptSnippet
      )

      expect(wrapper.find('iframe').exists()).toBe(false)
      expect(wrapper.get('script').text()).toBe('window.x = 1')
      expect(created).toBe(1)
    }
  )

  test('points the editor hint at the published application', async () => {
    const wrapper = await mountElement('editing')

    expect(
      wrapper
        .get('button[aria-label="iframeElementForm.editorEmbedHintPublished"]')
        .exists()
    ).toBe(true)
  })
})
