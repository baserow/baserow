import { mountSuspended } from '@nuxt/test-utils/runtime'
import TextField from '@baserow/modules/builder/components/elements/components/collectionField/TextField.vue'

describe('TextField', () => {
  const page = {}
  const builder = { id: 1, theme: {} }
  const mode = 'public'
  const element = { id: 1, type: 'table', fields: [], styles: {} }
  const field = { id: 1, uid: 'abc', name: 'Field', type: 'text', styles: {} }
  const value = '# Heading\n\n`inline code`'

  const mountComponent = (props = {}) =>
    mountSuspended(TextField, {
      props: { element, field, value, ...props },
      global: {
        provide: {
          workspace: {},
          builder,
          currentPage: page,
          elementPage: page,
          mode,
          applicationContext: { builder, page, mode },
        },
      },
    })

  test('renders Markdown with the Application Builder rules', async () => {
    const wrapper = await mountComponent({ format: 'markdown' })

    expect(wrapper.find('.ab-heading').text()).toBe('Heading')
    expect(wrapper.find('.ab-code--inline').text()).toBe('inline code')
    expect(wrapper.find('span.ab-text').exists()).toBe(false)
  })

  test('renders the raw text when the format is plain', async () => {
    const wrapper = await mountComponent({ format: 'plain' })

    const spans = wrapper.findAll('span.ab-text')
    expect(spans).toHaveLength(1)
    expect(spans[0].text()).toBe(value)
    expect(wrapper.find('.ab-heading').exists()).toBe(false)
    expect(wrapper.find('.markdown').exists()).toBe(false)
  })

  test('defaults to plain when no format is given', async () => {
    const wrapper = await mountComponent()

    expect(wrapper.find('span.ab-text').text()).toBe(value)
    expect(wrapper.find('.ab-heading').exists()).toBe(false)
  })
})
