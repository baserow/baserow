import { defineComponent } from 'vue'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import { flushPromises } from '@vue/test-utils'

import CoreManualTriggerServiceForm from '@baserow/modules/integrations/core/components/services/CoreManualTriggerServiceForm'

const FormGroupStub = defineComponent({
  name: 'FormGroup',
  template: '<div><slot /></div>',
})

const CheckboxStub = defineComponent({
  name: 'Checkbox',
  props: {
    modelValue: {
      type: Boolean,
      required: true,
    },
  },
  emits: ['update:modelValue'],
  template: '<button><slot /></button>',
})

const FormInputStub = defineComponent({
  name: 'FormInput',
  props: {
    modelValue: {
      type: Number,
      required: true,
    },
  },
  emits: ['update:modelValue'],
  template: '<input />',
})

async function mountComponent() {
  return await mountSuspended(CoreManualTriggerServiceForm, {
    global: {
      stubs: {
        FormGroup: FormGroupStub,
        Checkbox: CheckboxStub,
        FormInput: FormInputStub,
      },
      mocks: {
        $t: (key) => key,
      },
    },
  })
}

describe('CoreManualTriggerServiceForm', () => {
  test('only shows the timeout when waiting for a response is enabled', async () => {
    const wrapper = await mountComponent()

    expect(wrapper.findComponent({ name: 'FormInput' }).exists()).toBe(false)
    expect(wrapper.vm.values.response_timeout_seconds).toBe(30)

    wrapper
      .findComponent({ name: 'Checkbox' })
      .vm.$emit('update:modelValue', true)
    await flushPromises()

    expect(wrapper.vm.values.wait_for_response).toBe(true)
    expect(wrapper.findComponent({ name: 'FormInput' }).exists()).toBe(true)
  })
})
