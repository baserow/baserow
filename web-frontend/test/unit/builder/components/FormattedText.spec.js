import { mountSuspended } from '@nuxt/test-utils/runtime'
import FormattedText from '@baserow/modules/builder/components/FormattedText.vue'

describe('FormattedText', () => {
  const builder = { id: 7 }

  afterEach(() => {
    vi.restoreAllMocks()
  })

  const mountComponent = (props, { mode = 'public' } = {}) =>
    mountSuspended(FormattedText, {
      props,
      global: { provide: { builder, mode } },
    })

  const click = (wrapper, selector) => {
    const event = new MouseEvent('click', { bubbles: true, cancelable: true })
    wrapper.find(selector).element.dispatchEvent(event)
    return event
  }

  test('renders the raw text when the format is plain', async () => {
    const wrapper = await mountComponent({ content: '**bold** [x](/x)' })

    expect(wrapper.find('strong').exists()).toBe(false)
    expect(wrapper.find('a').exists()).toBe(false)
    expect(wrapper.text()).toBe('**bold** [x](/x)')
  })

  test('defaults to plain when no format is given', async () => {
    const wrapper = await mountComponent({ content: '**bold**' })

    expect(wrapper.text()).toBe('**bold**')
  })

  test('accepts numeric content', async () => {
    const wrapper = await mountComponent({ content: 5, format: 'markdown' })

    expect(wrapper.text()).toBe('5')
  })

  test('inline preset renders emphasis but keeps links and block syntax literal', async () => {
    const wrapper = await mountComponent({
      content: '# **Urgent** [docs](https://example.com) `code`',
      format: 'markdown',
      preset: 'inline',
    })

    expect(wrapper.element.tagName).toBe('SPAN')
    expect(wrapper.find('strong').text()).toBe('Urgent')
    expect(wrapper.find('.ab-code--inline').text()).toBe('code')
    expect(wrapper.find('a').exists()).toBe(false)
    expect(wrapper.find('h1').exists()).toBe(false)
    expect(wrapper.text()).toBe('# Urgent [docs](https://example.com) code')
  })

  test('inline presets render line breaks as spaces', async () => {
    const wrapper = await mountComponent({
      content: 'first  \nsecond\\\nthird',
      format: 'markdown',
      preset: 'inline',
    })

    expect(wrapper.find('br').exists()).toBe(false)
    expect(wrapper.text()).toBe('first second third')
  })

  test('inlineLinks preset renders links but keeps images literal', async () => {
    const wrapper = await mountComponent({
      content:
        'Agree to the [terms](/terms) and [docs](https://example.com) ![i](https://example.com/i.png "t")',
      format: 'markdown',
      preset: 'inlineLinks',
    })

    const links = wrapper.findAll('a.ab-link')
    expect(links).toHaveLength(2)
    expect(links[0].attributes('href')).toBe('/terms')
    expect(links[1].attributes('href')).toBe('https://example.com')
    expect(wrapper.find('img').exists()).toBe(false)
    expect(wrapper.text()).toContain('![i](https://example.com/i.png "t")')
  })

  test('prefixes internal links in preview mode', async () => {
    const wrapper = await mountComponent(
      { content: '[terms](/terms)', format: 'markdown', preset: 'inlineLinks' },
      { mode: 'preview' }
    )

    expect(wrapper.find('a.ab-link').attributes('href')).toBe(
      '/builder/preview/7/terms'
    )
  })

  test('explicit builder and mode props win over the injected ones', async () => {
    const wrapper = await mountComponent(
      {
        content: '[terms](/terms)',
        format: 'markdown',
        preset: 'inlineLinks',
        builder: { id: 9 },
        mode: 'preview',
      },
      { mode: 'public' }
    )

    expect(wrapper.find('a.ab-link').attributes('href')).toBe(
      '/builder/preview/9/terms'
    )
  })

  test('restrictedBlock preset drops layout-breaking blocks but keeps links and lists', async () => {
    const content = [
      '# Heading',
      '',
      'Some **text** with [a link](https://example.com)',
      '',
      '- item',
      '',
      '| a | b |',
      '|---|---|',
      '| 1 | 2 |',
      '',
      '```',
      'code',
      '```',
      '',
      '![i](https://example.com/i.png)',
    ].join('\n')
    const wrapper = await mountComponent({
      content,
      format: 'markdown',
      preset: 'restrictedBlock',
    })

    expect(wrapper.element.tagName).toBe('DIV')
    expect(wrapper.find('.ab-heading').exists()).toBe(false)
    expect(wrapper.find('table').exists()).toBe(false)
    expect(wrapper.find('pre').exists()).toBe(false)
    expect(wrapper.find('img').exists()).toBe(false)
    expect(wrapper.text()).toContain('![i](https://example.com/i.png)')
    expect(wrapper.find('p.ab-text').exists()).toBe(true)
    expect(wrapper.find('strong').text()).toBe('text')
    expect(wrapper.find('a.ab-link').attributes('href')).toBe(
      'https://example.com'
    )
    expect(wrapper.find('.ab-list__item').text()).toBe('item')
    expect(wrapper.text()).toContain('# Heading')
  })

  test('block preset renders the full syntax', async () => {
    const wrapper = await mountComponent({
      content: '# Heading\n\n| a |\n|---|\n| 1 |',
      format: 'markdown',
      preset: 'block',
    })

    expect(wrapper.find('.ab-heading').text()).toBe('Heading')
    expect(wrapper.find('table').exists()).toBe(true)
  })

  test('blocks link navigation in editing mode', async () => {
    const wrapper = await mountComponent(
      { content: '[terms](/terms)', format: 'markdown', preset: 'inlineLinks' },
      { mode: 'editing' }
    )

    const event = click(wrapper, 'a.ab-link')

    expect(event.defaultPrevented).toBe(true)
  })

  test('routes internal links through the router', async () => {
    const push = vi
      .spyOn(useNuxtApp().$router, 'push')
      .mockImplementation(() => Promise.resolve())
    const wrapper = await mountComponent({
      content: '[terms](/terms)',
      format: 'markdown',
      preset: 'inlineLinks',
    })

    const event = click(wrapper, 'a.ab-link')

    expect(event.defaultPrevented).toBe(true)
    expect(push).toHaveBeenCalledWith('/terms')
  })

  test('routes internal links through the router when nested markup is clicked', async () => {
    const push = vi
      .spyOn(useNuxtApp().$router, 'push')
      .mockImplementation(() => Promise.resolve())
    const wrapper = await mountComponent({
      content: '[**terms**](/terms)',
      format: 'markdown',
      preset: 'inlineLinks',
    })

    const event = click(wrapper, 'a.ab-link strong')

    expect(event.defaultPrevented).toBe(true)
    expect(push).toHaveBeenCalledWith('/terms')
  })

  test('ignores clicks outside links', async () => {
    const push = vi
      .spyOn(useNuxtApp().$router, 'push')
      .mockImplementation(() => Promise.resolve())
    const wrapper = await mountComponent({
      content: '**bold** [terms](/terms)',
      format: 'markdown',
      preset: 'inlineLinks',
    })

    const event = click(wrapper, 'strong')

    expect(event.defaultPrevented).toBe(false)
    expect(push).not.toHaveBeenCalled()
  })

  test('leaves external links to the browser', async () => {
    const push = vi
      .spyOn(useNuxtApp().$router, 'push')
      .mockImplementation(() => Promise.resolve())
    const wrapper = await mountComponent({
      content: '[docs](https://example.com)',
      format: 'markdown',
      preset: 'inlineLinks',
    })

    const event = click(wrapper, 'a.ab-link')

    expect(event.defaultPrevented).toBe(false)
    expect(push).not.toHaveBeenCalled()
  })
})
