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
    'shows a placeholder in the editor with local mode %s',
    async (mode) => {
      const wrapper = await mountElement(mode, 'editing')
      expect(wrapper.text()).toContain('htmlElement.placeholder')
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
    }
  )
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
