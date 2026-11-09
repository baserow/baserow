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
  test.each([
    ['', false],
    [snippet, true],
    ['<img id="anchor" onerror="alert(1)">', false],
  ])(
    'withholds empty, untrusted or invalid content',
    async (html, untrusted) => {
      const wrapper = await mountElement('preview', 'preview', html, untrusted)
      expect(wrapper.find('#anchor').exists()).toBe(false)
      expect(wrapper.text()).toBe('')
    }
  )
})
