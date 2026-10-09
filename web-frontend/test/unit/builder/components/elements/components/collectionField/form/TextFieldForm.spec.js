import { defineComponent } from 'vue'
import { mountSuspended } from '@nuxt/test-utils/runtime'

import TextFieldForm from '@baserow/modules/builder/components/elements/components/collectionField/form/TextFieldForm.vue'

const InjectedFormulaInputStub = defineComponent({
  name: 'InjectedFormulaInput',
  props: {
    modelValue: { type: Object, default: () => ({}) },
    placeholder: { type: String, default: '' },
    allowedFormats: { type: Array, default: () => ['plain'] },
  },
  template: '<div />',
})

describe('TextFieldForm', () => {
  const mountComponent = () => {
    return mountSuspended(TextFieldForm, {
      props: {
        defaultValues: { id: 1, value: {}, styles: {} },
        element: { id: 1, type: 'table', fields: [] },
        baseTheme: {},
      },
      global: {
        provide: {
          workspace: {},
          builder: { theme: {} },
          currentPage: {},
          elementPage: {},
          mode: 'editing',
          applicationContext: {},
        },
        stubs: {
          FormGroup: {
            template: '<div><slot /><slot name="after-input" /></div>',
          },
          InjectedFormulaInput: InjectedFormulaInputStub,
          CustomStyleButton: true,
        },
      },
    })
  }

  test('lets the value be formatted as markdown', async () => {
    const wrapper = await mountComponent()

    const input = wrapper.findComponent(InjectedFormulaInputStub)
    expect(input.props('placeholder')).toBe(
      'textFieldForm.fieldValuePlaceholder'
    )
    expect(input.props('allowedFormats')).toEqual(['plain', 'markdown'])

    wrapper.unmount()
  })
})
