import { mountSuspended } from '@nuxt/test-utils/runtime'
import MarkdownIt from '@baserow/modules/core/components/MarkdownIt.vue'

describe('MarkdownIt', () => {
  const mountComponent = (props) => mountSuspended(MarkdownIt, { props })

  test('renders block Markdown in a div by default', async () => {
    const wrapper = await mountComponent({
      content: '# Title\n\nSome **bold** text',
    })

    expect(wrapper.element.tagName).toBe('DIV')
    expect(wrapper.classes()).not.toContain('markdown--inline')
    expect(wrapper.find('h1').text()).toBe('Title')
    expect(wrapper.find('strong').text()).toBe('bold')
  })

  test('renders inline Markdown in a span and keeps block syntax literal', async () => {
    const wrapper = await mountComponent({
      content: '# Not a heading with **bold**',
      inline: true,
    })

    expect(wrapper.element.tagName).toBe('SPAN')
    expect(wrapper.classes()).toContain('markdown--inline')
    expect(wrapper.find('h1').exists()).toBe(false)
    expect(wrapper.find('strong').text()).toBe('bold')
    expect(wrapper.text()).toBe('# Not a heading with bold')
  })

  test('disables the given rules', async () => {
    const content =
      'See [docs](https://example.com) and ![img](https://example.com/i.png)'
    const wrapper = await mountComponent({
      content,
      inline: true,
      disabledRules: ['link', 'image'],
    })

    expect(wrapper.find('a').exists()).toBe(false)
    expect(wrapper.find('img').exists()).toBe(false)
    expect(wrapper.text()).toBe(content)
  })

  test('re-enables rules when disabledRules changes', async () => {
    const wrapper = await mountComponent({
      content: '[docs](https://example.com)',
      inline: true,
      disabledRules: ['link'],
    })
    expect(wrapper.find('a').exists()).toBe(false)

    await wrapper.setProps({ disabledRules: [] })

    expect(wrapper.find('a').exists()).toBe(true)
  })

  test('escapes raw HTML in inline mode', async () => {
    const wrapper = await mountComponent({
      content: '<b>not bold</b>',
      inline: true,
    })

    expect(wrapper.find('b').exists()).toBe(false)
    expect(wrapper.text()).toBe('<b>not bold</b>')
  })
})
