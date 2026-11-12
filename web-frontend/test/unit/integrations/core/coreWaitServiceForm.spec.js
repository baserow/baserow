import { defineComponent } from 'vue'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import { flushPromises } from '@vue/test-utils'

import CoreWaitServiceForm from '@baserow/modules/integrations/core/components/services/CoreWaitServiceForm'

const FormGroupStub = defineComponent({
  name: 'FormGroup',
  template: '<div><slot /></div>',
})

const InjectedFormulaInputStub = defineComponent({
  name: 'InjectedFormulaInput',
  props: {
    modelValue: {
      required: false,
      default: null,
    },
  },
  emits: ['update:modelValue'],
  template: '<div />',
})

async function mountForm({ defaultValues = {}, maxSeconds = 21600 } = {}) {
  return await mountSuspended(CoreWaitServiceForm, {
    props: { defaultValues },
    global: {
      stubs: {
        FormGroup: FormGroupStub,
        InjectedFormulaInput: InjectedFormulaInputStub,
      },
      mocks: {
        // Echoes the parameters so the assertions see which bound is shown.
        $t: (key, params) =>
          params ? `${key}:${JSON.stringify(params)}` : key,
        $config: { public: { automationWaitMaxSeconds: maxSeconds } },
      },
    },
  })
}

describe('CoreWaitServiceForm', () => {
  test('tells the designer the longest wait the instance allows', async () => {
    const wrapper = await mountForm({ maxSeconds: 3600 })
    await flushPromises()

    expect(wrapper.find('p').text()).toBe(
      'coreWaitServiceForm.secondsDescription:{"max":3600}'
    )
  })

  test('seeds the seconds formula from the saved service', async () => {
    const seconds = { formula: '60', mode: 'simple' }
    const wrapper = await mountForm({
      defaultValues: { id: 1, seconds, schema: {} },
    })
    await flushPromises()

    expect(
      wrapper
        .findComponent({ name: 'InjectedFormulaInput' })
        .props('modelValue')
    ).toEqual(seconds)
  })

  test('emits only the seconds when the formula changes', async () => {
    const wrapper = await mountForm({
      defaultValues: { id: 1, seconds: {}, schema: {} },
    })
    await flushPromises()
    const seconds = { formula: '60', mode: 'simple' }

    wrapper
      .findComponent({ name: 'InjectedFormulaInput' })
      .vm.$emit('update:modelValue', seconds)
    await flushPromises()

    expect(wrapper.emitted('values-changed').at(-1)).toEqual([{ seconds }])
  })
})
