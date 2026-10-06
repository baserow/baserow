import { mountSuspended } from '@nuxt/test-utils/runtime'
import TextField from '@baserow/modules/builder/components/elements/components/collectionField/TextField.vue'

describe('TextField collection field', () => {
  let wrapper = null

  afterEach(() => {
    wrapper?.unmount()
  })

  const mountField = async (value, field) => {
    const page = { id: 1, elements: [] }
    const builder = { id: 1, theme: {}, pages: [page] }
    const mode = 'public'

    wrapper = await mountSuspended(TextField, {
      props: {
        element: { id: 1, type: 'table', page_id: page.id },
        field,
        value,
      },
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
    return wrapper
  }

  test('renders a plain value as paragraphs without interpreting markdown', async () => {
    const wrapper = await mountField('**First**\nSecond', {
      value: { formula: '' },
    })

    expect(wrapper.element.tagName).toBe('DIV')
    expect(wrapper.findAll('p.ab-text').map((p) => p.text())).toEqual([
      '**First**',
      'Second',
    ])
    expect(wrapper.find('strong').exists()).toBe(false)
  })

  test('renders a markdown value', async () => {
    const wrapper = await mountField('**First**\n\nSecond', {
      value: { formula: '', format: 'markdown' },
    })

    expect(wrapper.element.tagName).toBe('DIV')
    expect(wrapper.find('p.ab-text strong').text()).toBe('First')
    expect(wrapper.findAll('p.ab-text')).toHaveLength(2)
  })
})
