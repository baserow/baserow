import { reactive } from 'vue'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import CheckboxElement from '@baserow/modules/builder/components/elements/components/CheckboxElement.vue'

describe('CheckboxElement', () => {
  let store = null
  let wrapper = null

  beforeEach(() => {
    store = useNuxtApp().$store
  })

  afterEach(() => {
    wrapper?.unmount()
  })

  const mountCheckbox = async (label, { required = false } = {}) => {
    const page = reactive({ id: 1, elements: [] })
    const builder = { id: 1, theme: { primary_color: '#ccc' }, pages: [page] }
    const mode = 'public'
    const element = {
      id: 42,
      type: 'checkbox',
      label,
      default_value: { formula: '' },
      required,
      page_id: page.id,
      styles: {},
    }

    store.dispatch('element/forceCreate', { page, element })

    wrapper = await mountSuspended(CheckboxElement, {
      props: { element },
      global: {
        provide: {
          builder,
          currentPage: page,
          elementPage: page,
          mode,
          applicationContext: { builder, page, mode },
          element,
          workspace: {},
        },
      },
    })
    return wrapper
  }

  test('renders a plain label without interpreting markdown', async () => {
    const wrapper = await mountCheckbox({ formula: "'I **agree**'" })

    const label = wrapper.find('.ab-checkbox__label')
    expect(label.text()).toBe('I **agree**')
    expect(label.find('strong').exists()).toBe(false)
  })

  test('renders a markdown label inline', async () => {
    const wrapper = await mountCheckbox({
      formula: "'I **agree** to the [terms](https://baserow.io)'",
      format: 'markdown',
    })

    const label = wrapper.find('.ab-checkbox__label')
    expect(label.find('strong').text()).toBe('agree')
    expect(label.find('a.ab-link').attributes('href')).toBe(
      'https://baserow.io'
    )
    expect(label.find('p').exists()).toBe(false)
  })

  test('marks a required checkbox with an asterisk after the label', async () => {
    const wrapper = await mountCheckbox(
      { formula: "'I **agree**'", format: 'markdown' },
      { required: true }
    )

    const label = wrapper.find('.ab-checkbox__label')
    expect(label.text()).toBe('I agree *')
    expect(label.find('span[title="error.requiredField"]').exists()).toBe(true)
  })
})
