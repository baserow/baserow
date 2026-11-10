import { mountSuspended } from '@nuxt/test-utils/runtime'
import { enableAutoUnmount } from '@vue/test-utils'
import HTMLElement from '@baserow_enterprise/builder/components/elements/HTMLElement'

enableAutoUnmount(afterEach)

const snippet =
  '<section id="anchor" class="widget" data-lang="en" aria-label="Demo">Widget</section>'

function mountElement(
  mode,
  contextMode = mode,
  html = snippet,
  untrusted = false
) {
  return mountSuspended(HTMLElement, {
    props: { element: { type: 'html', html } },
    global: {
      provide: {
        mode,
        builder: { untrusted_content: untrusted },
        applicationContext: { mode: contextMode },
      },
    },
  })
}

describe('HTML element', () => {
  test.each(['editing', 'public'])(
    'isolates editor HTML in a script-disabled iframe with local mode %s',
    async (mode) => {
      const wrapper = await mountElement(mode, 'editing')
      const frame = wrapper.get('iframe')
      expect(frame.attributes('srcdoc')).toBe(snippet)
      expect(frame.attributes('sandbox')).toBe('allow-same-origin')
      expect(frame.attributes('tabindex')).toBe('-1')
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

  test('waits for an explicit visitor context before inserting markup', async () => {
    const wrapper = await mountElement('public', '')
    expect(wrapper.find('#anchor').exists()).toBe(false)
  })

  test.each([
    ['', false],
    [snippet, true],
    ['<img id="anchor" onerror="alert(1)">', false],
    ['<a id="anchor" href="java&#9;script:alert(1)">Open</a>', false],
    ['<img id="anchor" srcset="/pic.png 1x, javascript:alert(1) 2x">', false],
    ['<iframe id="anchor" srcdoc="&lt;body onload=alert(1)>"></iframe>', false],
    [
      '<svg id="anchor"><set attributeName="href" to="javascript:alert(1)" /></svg>',
      false,
    ],
  ])(
    'withholds empty, untrusted or invalid content',
    async (html, untrusted) => {
      const wrapper = await mountElement('preview', 'preview', html, untrusted)
      expect(wrapper.find('#anchor').exists()).toBe(false)
      expect(wrapper.text()).toBe('')
    }
  )
})
