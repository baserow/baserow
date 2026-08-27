import { mountSuspended } from '@nuxt/test-utils/runtime'
import TagsField from '@baserow/modules/builder/components/elements/components/collectionField/TagsField.vue'

describe('TagsField', () => {
  const page = {}
  const builder = { id: 1, theme: {} }
  const mode = 'public'
  const element = { id: 1, type: 'table', fields: [], styles: {} }
  const field = { id: 1, uid: 'abc', name: 'Field', type: 'tags', styles: {} }
  const tags = [
    { value: '**urgent**', color: '#ff0000' },
    { value: 'see [docs](https://example.com)', color: '#00ff00' },
  ]

  const mountComponent = (props = {}) =>
    mountSuspended(TagsField, {
      props: { element, field, tags, ...props },
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

  test('renders inline Markdown without links when the format is markdown', async () => {
    const wrapper = await mountComponent({ format: 'markdown' })

    const [urgent, docs] = wrapper.findAll('.ab-tag')
    expect(urgent.find('strong').text()).toBe('urgent')
    expect(urgent.find('.markdown--inline').exists()).toBe(true)
    expect(docs.find('a').exists()).toBe(false)
    expect(docs.text()).toBe('see [docs](https://example.com)')
  })

  test('renders the raw text when the format is plain', async () => {
    const wrapper = await mountComponent({ format: 'plain' })

    const [urgent] = wrapper.findAll('.ab-tag')
    expect(urgent.find('strong').exists()).toBe(false)
    expect(urgent.text()).toBe('**urgent**')
  })

  test('defaults to plain when no format is given', async () => {
    const wrapper = await mountComponent()

    expect(wrapper.findAll('.ab-tag')[0].text()).toBe('**urgent**')
    expect(wrapper.find('.markdown').exists()).toBe(false)
  })
})
