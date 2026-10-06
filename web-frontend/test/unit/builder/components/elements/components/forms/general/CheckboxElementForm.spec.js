import { defineComponent } from 'vue'
import { mountSuspended } from '@nuxt/test-utils/runtime'

import CheckboxElementForm from '@baserow/modules/builder/components/elements/components/forms/general/CheckboxElementForm.vue'

const InjectedFormulaInputStub = defineComponent({
  name: 'InjectedFormulaInput',
  props: {
    modelValue: { type: Object, default: () => ({}) },
    placeholder: { type: String, default: '' },
    allowedFormats: { type: Array, default: () => ['plain'] },
  },
  template: '<div />',
})

describe('CheckboxElementForm', () => {
  const mountComponent = () => {
    return mountSuspended(CheckboxElementForm, {
      props: {
        defaultValues: {
          label: {},
          default_value: {},
          required: false,
          styles: {},
        },
      },
      global: {
        provide: {
          workspace: {},
          builder: { theme: {} },
          currentPage: {},
          elementPage: {},
          mode: 'editing',
        },
        stubs: {
          FormGroup: { template: '<div><slot /></div>' },
          InjectedFormulaInput: InjectedFormulaInputStub,
          CustomStyleButton: true,
          Checkbox: true,
        },
      },
    })
  }

  test('only lets the label be formatted as markdown', async () => {
    const wrapper = await mountComponent()

    const inputs = wrapper.findAllComponents(InjectedFormulaInputStub)
    expect(
      inputs.map((input) => [
        input.props('placeholder'),
        input.props('allowedFormats'),
      ])
    ).toEqual([
      ['generalForm.labelPlaceholder', ['plain', 'markdown']],
      ['generalForm.valuePlaceholder', ['plain']],
    ])

    wrapper.unmount()
  })
})
