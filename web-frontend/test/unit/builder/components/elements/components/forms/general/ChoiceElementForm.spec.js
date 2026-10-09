import { defineComponent } from 'vue'
import { mountSuspended } from '@nuxt/test-utils/runtime'

import { CHOICE_OPTION_TYPES } from '@baserow/modules/builder/enums'
import ChoiceElementForm from '@baserow/modules/builder/components/elements/components/forms/general/ChoiceElementForm.vue'

const InjectedFormulaInputStub = defineComponent({
  name: 'InjectedFormulaInput',
  props: {
    modelValue: { type: Object, default: () => ({}) },
    placeholder: { type: String, default: '' },
    allowedFormats: { type: Array, default: () => ['plain'] },
  },
  template: '<div />',
})

describe('ChoiceElementForm', () => {
  const mountComponent = (defaultValues = {}) => {
    return mountSuspended(ChoiceElementForm, {
      props: {
        defaultValues: {
          label: {},
          default_value: {},
          required: false,
          placeholder: {},
          options: [],
          multiple: false,
          show_as_dropdown: true,
          option_type: CHOICE_OPTION_TYPES.FORMULAS,
          formula_name: {},
          formula_value: {},
          styles: {},
          ...defaultValues,
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
          RadioGroup: true,
        },
      },
    })
  }

  test('lets the label and the formula option names be formatted as markdown', async () => {
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
      ['generalForm.placeholderPlaceholder', ['plain']],
      ['choiceOptionSelector.namePlaceholder', ['plain', 'markdown']],
      ['choiceOptionSelector.valuePlaceholder', ['plain']],
    ])

    wrapper.unmount()
  })
})
