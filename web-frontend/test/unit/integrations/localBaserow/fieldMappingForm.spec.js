import { h } from 'vue'
import { TestApp } from '@baserow/test/helpers/testApp'
import FieldMappingForm from '@baserow/modules/integrations/localBaserow/components/services/FieldMappingForm'

const FIELD = { id: 1, name: 'Name', type: 'text' }
const MAPPING = { field_id: 1, enabled: true, value: { formula: "'before'" } }

describe('FieldMappingForm', () => {
  let testApp = null

  beforeEach(() => {
    vi.useFakeTimers()
    testApp = new TestApp()
  })

  afterEach(async () => {
    vi.useRealTimers()
    await testApp.afterEach()
  })

  const mountForm = async () =>
    testApp.mount(FieldMappingForm, {
      props: { field: FIELD, mapping: MAPPING },
      global: {
        provide: {
          workspace: { id: 1 },
          formulaComponent: () => h('div', 'fake formula component'),
          dataProvidersAllowed: [],
        },
        stubs: {
          // Its observer never fires here, so the input would never render.
          InViewport: { template: '<div><slot /></div>' },
        },
      },
    })

  const formulaInput = (wrapper) =>
    wrapper.findComponent({ name: 'InjectedFormulaInput' })

  const type = async (wrapper, formula) => {
    formulaInput(wrapper).vm.$emit('update:modelValue', { formula })
    await wrapper.vm.$nextTick()
  }

  test('an edit is held back while the user is still typing', async () => {
    const wrapper = await mountForm()

    await type(wrapper, "'after'")

    expect(wrapper.emitted('update')).toBeUndefined()
  })

  test('leaving the field applies the edit without waiting for the timer', async () => {
    // Clicking Save is what takes the focus off this input.
    const wrapper = await mountForm()

    await type(wrapper, "'after'")
    formulaInput(wrapper).vm.$emit('blur')
    await wrapper.vm.$nextTick()

    expect(wrapper.emitted('update')).toEqual([
      [{ value: { formula: "'after'" } }],
    ])
  })

  test('the edit is applied once, not again when the timer catches up', async () => {
    const wrapper = await mountForm()

    await type(wrapper, "'after'")
    formulaInput(wrapper).vm.$emit('blur')
    vi.advanceTimersByTime(1000)
    await wrapper.vm.$nextTick()

    expect(wrapper.emitted('update')).toHaveLength(1)
  })

  test('leaving an untouched field changes nothing', async () => {
    const wrapper = await mountForm()

    formulaInput(wrapper).vm.$emit('blur')
    await wrapper.vm.$nextTick()

    expect(wrapper.emitted('update')).toBeUndefined()
  })
})
