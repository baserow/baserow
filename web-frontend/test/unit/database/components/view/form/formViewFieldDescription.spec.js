import { TestApp } from '@baserow/test/helpers/testApp'
import FormViewField from '@baserow/modules/database/components/view/form/FormViewField'

// Stub the description editor: the toggle/save behavior is covered by
// formViewDescription.spec.js, here we only check how FormViewField wires it up.
const FormViewDescriptionStub = {
  name: 'FormViewDescription',
  props: {
    value: { type: String, default: '' },
    readOnly: { type: Boolean, default: false },
    placeholder: { type: String, default: '' },
  },
  emits: ['change'],
  template: '<div class="form-view-description-stub"></div>',
}

describe('FormViewField description', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const field = {
    id: 1,
    name: 'Name',
    type: 'text',
    _: { type: { iconClass: '' } },
  }

  const mountComponent = (fieldOptions = {}) =>
    testApp.mount(FormViewField, {
      props: {
        database: { workspace: { id: 1 } },
        table: { id: 1 },
        view: { slug: 'abc' },
        field,
        fields: [field],
        fieldOptions: {
          description: '**bold**',
          conditions: [],
          condition_groups: [],
          ...fieldOptions,
        },
        readOnly: false,
      },
      global: { stubs: { FormViewDescription: FormViewDescriptionStub } },
    })

  test('forwards the stored markdown description to the editor', async () => {
    const wrapper = await mountComponent({ description: '**bold**' })
    const description = wrapper.findComponent(FormViewDescriptionStub)
    expect(description.exists()).toBe(true)
    expect(description.props('value')).toBe('**bold**')
  })

  test('does not render the description for an unselected field with no description', async () => {
    const wrapper = await mountComponent({ description: '' })
    // v-if keeps the description out of the DOM until the field is selected.
    expect(wrapper.findComponent(FormViewDescriptionStub).exists()).toBe(false)
    await wrapper.find('.form-view__field').trigger('click')
    expect(wrapper.findComponent(FormViewDescriptionStub).exists()).toBe(true)
  })

  test('emits updated-field-options with markdown when the editor changes', async () => {
    const wrapper = await mountComponent({ description: '' })
    await wrapper.find('.form-view__field').trigger('click')
    const description = wrapper.findComponent(FormViewDescriptionStub)
    description.vm.$emit('change', 'See [docs](https://baserow.io)')
    await wrapper.vm.$nextTick()

    const events = wrapper.emitted('updated-field-options')
    expect(events).toBeTruthy()
    expect(events[events.length - 1][0]).toEqual({
      description: 'See [docs](https://baserow.io)',
    })
  })
})
