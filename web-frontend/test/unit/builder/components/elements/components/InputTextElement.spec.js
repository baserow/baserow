import { mountSuspended } from '@nuxt/test-utils/runtime'
import InputTextElement from '@baserow/modules/builder/components/elements/components/InputTextElement.vue'

describe('InputTextElement', () => {
  let store = null

  beforeEach(() => {
    store = useNuxtApp().$store
  })

  const mountComponent = ({ props = {}, provide = {} }) => {
    return mountSuspended(InputTextElement, {
      props,
      global: { provide },
    })
  }

  const mountNumericInput = async (defaultValue) => {
    const page = { id: 1, elements: [] }
    const builder = { id: 1, theme: { primary_color: '#ccc' }, pages: [page] }
    const workspace = {}
    const mode = 'public'
    const element = {
      id: 42,
      type: 'input_text',
      validation_type: 'integer',
      default_value: { formula: defaultValue },
      label: { formula: '' },
      placeholder: { formula: '' },
      required: false,
      is_multiline: false,
      rows: 1,
      input_type: 'number',
      page_id: page.id,
      styles: {},
    }

    store.dispatch('element/forceCreate', { page, element })

    return mountComponent({
      props: { element },
      provide: {
        builder,
        currentPage: page,
        elementPage: page,
        mode,
        applicationContext: { builder, page, mode },
        element,
        workspace,
      },
    })
  }

  test.each([
    ['0', '0'],
    ['', ''],
  ])(
    'renders numeric default value %p as %p',
    async (defaultValue, expected) => {
      const wrapper = await mountNumericInput(defaultValue)

      expect(wrapper.find('input').element.value).toBe(expected)
    }
  )
})

describe('InputTextElement label', () => {
  let store = null

  beforeEach(() => {
    store = useNuxtApp().$store
  })

  const mountWithLabel = async (labelFormat) => {
    const page = { id: 1, elements: [] }
    const builder = { id: 1, theme: { primary_color: '#ccc' }, pages: [page] }
    const workspace = {}
    const mode = 'public'
    const element = {
      id: 43,
      type: 'input_text',
      validation_type: 'any',
      default_value: { formula: '' },
      label: { mode: 'raw', formula: 'Your **name** ([why?](/why))' },
      label_format: labelFormat,
      placeholder: { formula: '' },
      required: false,
      is_multiline: false,
      rows: 1,
      input_type: 'text',
      page_id: page.id,
      styles: {},
    }

    store.dispatch('element/forceCreate', { page, element })

    return mountSuspended(InputTextElement, {
      props: { element },
      global: {
        provide: {
          builder,
          currentPage: page,
          elementPage: page,
          mode,
          applicationContext: { builder, page, mode },
          element,
          workspace,
        },
      },
    })
  }

  test('renders the raw label by default', async () => {
    const wrapper = await mountWithLabel(undefined)

    const label = wrapper.find('.ab-form-group__label')
    expect(label.find('strong').exists()).toBe(false)
    expect(label.text()).toBe('Your **name** ([why?](/why))')
  })

  test('renders a Markdown label with links', async () => {
    const wrapper = await mountWithLabel('markdown')

    const label = wrapper.find('.ab-form-group__label')
    expect(label.find('strong').text()).toBe('name')
    expect(label.find('a.ab-link').attributes('href')).toBe('/why')
  })
})
