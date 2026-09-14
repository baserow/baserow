import { reactive } from 'vue'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import InputTextElement from '@baserow/modules/builder/components/elements/components/InputTextElement.vue'

describe('InputTextElement', () => {
  let store = null

  beforeEach(() => {
    store = useNuxtApp().$store
  })

  const mountComponent = ({ props = {}, provide = {}, locale = 'en' }) => {
    return mountSuspended(InputTextElement, {
      props,
      global: { provide, mocks: { $i18n: { locale } } },
    })
  }

  const mountNumericInput = async (defaultValue, locale = 'en') => {
    const page = reactive({ id: 1, elements: [] })
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
      input_type: 'text',
      page_id: page.id,
      styles: {},
    }

    store.dispatch('element/forceCreate', { page, element })

    return mountComponent({
      locale,
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
    ['en', '3,2', '3.2'],
    ['en', '3,2,.2,', '3.2'],
    ['de', '3.2', '3,2'],
    ['es', '3.2', '3,2'],
  ])(
    'shows an inline error for invalid %s input %s',
    async (locale, value, correction) => {
      const wrapper = await mountNumericInput('', locale)
      try {
        await wrapper.get('input').setValue(value)
        await wrapper.get('input').trigger('blur')
        expect(wrapper.get('input').element.value).toBe(value)
        expect(wrapper.text()).toContain('error.invalidNumber')

        await wrapper.get('input').setValue(correction)
        expect(wrapper.text()).not.toContain('error.invalidNumber')

        await wrapper.get('input').setValue(value)
        expect(wrapper.text()).toContain('error.invalidNumber')
        await wrapper.get('input').setValue('')
        expect(wrapper.text()).not.toContain('error.invalidNumber')
      } finally {
        wrapper.unmount()
      }
    }
  )

  test.each([
    ['0', '0'],
    ['', ''],
  ])(
    'renders numeric default value %p as %p',
    async (defaultValue, expected) => {
      const wrapper = await mountNumericInput(defaultValue)

      try {
        expect(wrapper.find('input').element.value).toBe(expected)
      } finally {
        wrapper.unmount()
      }
    }
  )
})
