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
    wrapper = null
  })

  const mountCheckbox = async ({ mode = 'public', ...elementOverrides }) => {
    const page = { id: 1, elements: [] }
    const builder = { id: 1, theme: { primary_color: '#ccc' }, pages: [page] }
    const applicationContext = { builder, page, mode }
    const element = {
      id: 42,
      type: 'checkbox',
      label: { mode: 'raw', formula: 'I agree to the [terms](/terms)' },
      label_format: 'plain',
      default_value: { formula: '' },
      required: false,
      page_id: page.id,
      styles: {},
      ...elementOverrides,
    }

    store.dispatch('element/forceCreate', { page, element })
    const elementType = store.$registry.get('element', 'checkbox')
    store.dispatch('formData/setFormData', {
      page,
      elementId: element.id,
      payload: {
        value: false,
        type: elementType.formDataType(element),
        isValid: elementType.isValid(element, false, applicationContext),
        touched: false,
      },
    })

    // Attached to the document so that the native `label[for]` activation
    // behaviour applies when clicking the label.
    return mountSuspended(CheckboxElement, {
      props: { element },
      attachTo: document.body,
      global: {
        provide: {
          builder,
          currentPage: page,
          elementPage: page,
          mode,
          applicationContext,
          element,
          workspace: {},
        },
      },
    })
  }

  const click = (wrapper, selector) => {
    const event = new MouseEvent('click', { bubbles: true, cancelable: true })
    wrapper.find(selector).element.dispatchEvent(event)
    return event
  }

  test('renders the raw label when the format is plain', async () => {
    wrapper = await mountCheckbox({})

    expect(wrapper.find('.ab-checkbox__label a').exists()).toBe(false)
    expect(wrapper.find('.ab-checkbox__label').text()).toBe(
      'I agree to the [terms](/terms)'
    )
  })

  test('renders a Markdown label with links', async () => {
    wrapper = await mountCheckbox({ label_format: 'markdown' })

    const link = wrapper.find('.ab-checkbox__label a.ab-link')
    expect(link.text()).toBe('terms')
    expect(link.attributes('href')).toBe('/terms')
  })

  test('clicking the label text toggles the checkbox, clicking the link does not', async () => {
    wrapper = await mountCheckbox({ label_format: 'markdown' })
    expect(wrapper.vm.inputValue).toBe(false)

    click(wrapper, '.ab-checkbox__label')
    await wrapper.vm.$nextTick()
    expect(wrapper.vm.inputValue).toBe(true)

    click(wrapper, '.ab-checkbox__label a.ab-link')
    await wrapper.vm.$nextTick()
    expect(wrapper.vm.inputValue).toBe(true)
  })

  test('blocks link navigation in editing mode', async () => {
    wrapper = await mountCheckbox({
      label_format: 'markdown',
      mode: 'editing',
    })

    const event = click(wrapper, '.ab-checkbox__label a.ab-link')

    expect(event.defaultPrevented).toBe(true)
  })
})
