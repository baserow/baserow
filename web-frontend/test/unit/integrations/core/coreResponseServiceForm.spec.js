import { defineComponent } from 'vue'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import { flushPromises } from '@vue/test-utils'

import CoreResponseServiceForm from '@baserow/modules/integrations/core/components/services/CoreResponseServiceForm'

const FormGroupStub = defineComponent({
  name: 'FormGroup',
  template: '<div><slot /></div>',
})

const InjectedFormulaInputStub = defineComponent({
  name: 'InjectedFormulaInput',
  props: {
    modelValue: {
      type: Object,
      required: true,
    },
    allowRawValues: {
      type: Boolean,
      default: false,
    },
  },
  emits: ['update:modelValue'],
  methods: {
    input(value) {
      this.$emit('update:modelValue', {
        ...this.modelValue,
        formula: value,
      })
    },
  },
  template:
    '<div><slot name="raw-input" :value="modelValue.formula" :disabled="false" :input="input" /></div>',
})

const DropdownStub = defineComponent({
  name: 'Dropdown',
  props: {
    modelValue: {
      type: String,
      required: false,
      default: null,
    },
  },
  emits: ['update:modelValue'],
  template: '<div><slot /></div>',
})

const DropdownItemStub = defineComponent({
  name: 'DropdownItem',
  props: {
    name: {
      type: String,
      required: true,
    },
    value: {
      type: String,
      required: true,
    },
  },
  template: '<div />',
})

async function mountComponent() {
  return await mountSuspended(CoreResponseServiceForm, {
    global: {
      stubs: {
        FormGroup: FormGroupStub,
        InjectedFormulaInput: InjectedFormulaInputStub,
        Dropdown: DropdownStub,
        DropdownItem: DropdownItemStub,
        ButtonIcon: true,
        ButtonText: true,
      },
      mocks: {
        $t: (key) => key,
      },
    },
  })
}

describe('CoreResponseServiceForm', () => {
  test('defaults to a raw 204 status code and proposes common HTTP codes', async () => {
    const wrapper = await mountComponent()
    await flushPromises()

    const formulaInput = wrapper.findComponent({
      name: 'InjectedFormulaInput',
    })
    const dropdown = wrapper.findComponent({ name: 'Dropdown' })
    const statusCodes = dropdown
      .findAllComponents({ name: 'DropdownItem' })
      .map((item) => item.props('value'))

    expect(formulaInput.props('allowRawValues')).toBe(true)
    expect(wrapper.vm.values.status_code).toEqual({
      formula: '204',
      mode: 'raw',
    })
    expect(dropdown.props('modelValue')).toBe('204')
    expect(statusCodes).toEqual([
      '200',
      '201',
      '202',
      '204',
      '400',
      '401',
      '403',
      '404',
      '405',
      '409',
      '422',
      '429',
    ])
  })

  test('updates the raw formula when a status code is selected', async () => {
    const wrapper = await mountComponent()
    const dropdown = wrapper.findComponent({ name: 'Dropdown' })

    dropdown.vm.$emit('update:modelValue', '404')
    await flushPromises()

    expect(wrapper.vm.values.status_code).toEqual({
      formula: '404',
      mode: 'raw',
    })
  })
})
