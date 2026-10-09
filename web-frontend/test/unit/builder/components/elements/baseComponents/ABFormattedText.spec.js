import { nextTick } from 'vue'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import ABFormattedText from '@baserow/modules/builder/components/elements/baseComponents/ABFormattedText.vue'

describe('ABFormattedText', () => {
  const mountComponent = ({ props = {}, attrs = {}, provide = {} }) => {
    return mountSuspended(ABFormattedText, {
      props,
      attrs,
      global: { provide },
    })
  }

  describe('plain format', () => {
    test('renders the value as it is in a span in the inline profile', async () => {
      const wrapper = await mountComponent({
        props: { value: '**not bold**' },
      })

      expect(wrapper.element.tagName).toBe('SPAN')
      expect(wrapper.text()).toBe('**not bold**')
      expect(wrapper.find('strong').exists()).toBe(false)
    })

    test('renders one paragraph per line in the block profile', async () => {
      const wrapper = await mountComponent({
        props: { value: 'First\n\n  Second  \n', profile: 'block' },
      })

      expect(wrapper.element.tagName).toBe('DIV')
      expect(wrapper.findAll('p.ab-text').map((p) => p.text())).toEqual([
        'First',
        'Second',
      ])
    })
  })

  describe('markdown format', () => {
    test('renders inline markdown without breaking the line', async () => {
      const wrapper = await mountComponent({
        props: {
          value: '**bold** line  \nbreak ![alt](https://example.com/a.png)',
          format: 'markdown',
        },
      })

      expect(wrapper.element.tagName).toBe('SPAN')
      expect(wrapper.classes()).toContain('markdown--inline')
      expect(wrapper.find('strong').text()).toBe('bold')
      expect(wrapper.find('p').exists()).toBe(false)
      expect(wrapper.find('br').exists()).toBe(false)
      expect(wrapper.find('img').exists()).toBe(false)
    })

    test('renders block markdown with the Application Builder rules', async () => {
      const wrapper = await mountComponent({
        props: {
          value: '# Title\n\nSome `code`',
          format: 'markdown',
          profile: 'block',
        },
      })

      expect(wrapper.element.tagName).toBe('DIV')
      expect(wrapper.find('.ab-heading--h1').text()).toBe('Title')
      expect(wrapper.find('p.ab-text .ab-code--inline').text()).toBe('code')
    })

    test('renders links by default', async () => {
      const wrapper = await mountComponent({
        props: { value: '[Baserow](https://baserow.io)', format: 'markdown' },
      })

      const link = wrapper.find('a.ab-link')
      expect(link.text()).toBe('Baserow')
      expect(link.attributes('href')).toBe('https://baserow.io')
    })

    test('renders links as text when links are not allowed', async () => {
      const wrapper = await mountComponent({
        props: {
          value: '[Baserow](https://baserow.io) <https://baserow.io>',
          format: 'markdown',
          allowLinks: false,
        },
      })

      expect(wrapper.find('a').exists()).toBe(false)
      expect(wrapper.text()).toBe(
        '[Baserow](https://baserow.io) <https://baserow.io>'
      )
    })

    test('prefixes internal links in preview mode', async () => {
      const wrapper = await mountComponent({
        props: { value: '[Page](/path)', format: 'markdown' },
        provide: { builder: { id: 42 }, mode: 'preview' },
      })

      expect(wrapper.find('a.ab-link').attributes('href')).toBe(
        '/builder/preview/42/path'
      )
    })
  })

  test('falls back to plain text for an unknown format', async () => {
    // The prop validator warns about the format; the text still shows.
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    try {
      const wrapper = await mountComponent({
        props: { value: '**bold**', format: 'html' },
      })

      expect(wrapper.element.tagName).toBe('SPAN')
      expect(wrapper.text()).toBe('**bold**')
    } finally {
      warn.mockRestore()
    }
  })

  test.each(['plain', 'markdown'])(
    'puts its attributes on the root element of the %s renderer',
    async (format) => {
      const wrapper = await mountComponent({
        props: { value: 'Help', format, profile: 'block' },
        attrs: { class: 'ab-file-input__help-text', title: 'Help' },
      })

      expect(wrapper.element.tagName).toBe('DIV')
      expect(wrapper.classes()).toContain('ab-file-input__help-text')
      expect(wrapper.attributes('title')).toBe('Help')
    }
  )

  describe('link clicks', () => {
    let push = null

    beforeEach(() => {
      push = vi.spyOn(useRouter(), 'push').mockResolvedValue()
    })

    afterEach(() => {
      push.mockRestore()
    })

    const mountLink = (href, mode) => {
      return mountComponent({
        props: { value: `[Link](${href})`, format: 'markdown' },
        provide: { mode, builder: { id: 1 } },
      })
    }

    const clickLink = async (wrapper) => {
      const event = new MouseEvent('click', { bubbles: true, cancelable: true })
      const stopPropagation = vi.spyOn(event, 'stopPropagation')
      wrapper.find('a.ab-link').element.dispatchEvent(event)
      await nextTick()
      return { event, stopPropagation }
    }

    test('follows an internal link through the router', async () => {
      const wrapper = await mountLink('/path', 'public')

      const { event, stopPropagation } = await clickLink(wrapper)

      expect(push).toHaveBeenCalledWith('/path')
      expect(event.defaultPrevented).toBe(true)
      // Nothing above the text, like a drop zone, may act on the click too.
      expect(stopPropagation).toHaveBeenCalled()
    })

    test('keeps the click of an external link to itself', async () => {
      const wrapper = await mountLink('https://baserow.io', 'public')
      // Keep jsdom from trying to navigate to the external page.
      wrapper.element.addEventListener(
        'click',
        (event) => event.preventDefault(),
        true
      )

      const { stopPropagation } = await clickLink(wrapper)

      expect(push).not.toHaveBeenCalled()
      expect(stopPropagation).toHaveBeenCalled()
    })

    test('only prevents navigating in editing mode, so the editor can select the element', async () => {
      const wrapper = await mountLink('/path', 'editing')

      const { event, stopPropagation } = await clickLink(wrapper)

      expect(event.defaultPrevented).toBe(true)
      expect(stopPropagation).not.toHaveBeenCalled()
      expect(push).not.toHaveBeenCalled()
    })
  })
})
