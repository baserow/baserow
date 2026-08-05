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
