import { TestApp } from '@baserow/test/helpers/testApp'
import MarkdownIt from '@baserow/modules/core/components/MarkdownIt.vue'

describe('MarkdownIt.vue', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const mountComponent = (props = {}) => {
    return testApp.mount(MarkdownIt, {
      props: { content: '', ...props },
    })
  }

  it('renders block markdown in a div with paragraphs', async () => {
    const wrapper = await mountComponent({ content: '**bold**' })

    expect(wrapper.element.tagName).toBe('DIV')
    expect(wrapper.classes()).toEqual(['markdown'])
    expect(wrapper.find('p strong').text()).toBe('bold')
  })

  it('renders inline markdown in a span without paragraphs', async () => {
    const wrapper = await mountComponent({ content: '**bold**', inline: true })

    expect(wrapper.element.tagName).toBe('SPAN')
    expect(wrapper.classes()).toEqual(['markdown', 'markdown--inline'])
    expect(wrapper.find('p').exists()).toBe(false)
    expect(wrapper.find('strong').text()).toBe('bold')
  })

  it('leaves out the syntax of the disabled rules', async () => {
    // With only `image` off, markdown-it would still render the `[alt](url)`
    // part of the syntax as a link.
    const wrapper = await mountComponent({
      content: '![alt](https://example.com/a.png)',
      inline: true,
      disabledRules: ['image', 'link'],
    })

    expect(wrapper.find('img').exists()).toBe(false)
    expect(wrapper.find('a').exists()).toBe(false)
    expect(wrapper.text()).toBe('![alt](https://example.com/a.png)')
  })

  it('re-renders when the disabled rules change', async () => {
    const wrapper = await mountComponent({
      content: '![alt](https://example.com/a.png)',
      inline: true,
    })
    expect(wrapper.find('img').exists()).toBe(true)

    await wrapper.setProps({ disabledRules: ['image'] })

    expect(wrapper.find('img').exists()).toBe(false)
  })

  it('emits the clicks on the rendered content', async () => {
    const wrapper = await mountComponent({ content: '**bold**', inline: true })

    await wrapper.find('strong').trigger('click')

    expect(wrapper.emitted('click')).toHaveLength(1)
  })
})
