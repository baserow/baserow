import { defineComponent } from 'vue'
import { mountSuspended } from '@nuxt/test-utils/runtime'

import NotificationWorkflowActionForm from '@baserow/modules/builder/components/workflowAction/NotificationWorkflowActionForm'

const FormGroupStub = defineComponent({
  name: 'FormGroup',
  props: {
    required: Boolean,
  },
  template: '<div><slot /></div>',
})

const InjectedFormulaInputStub = defineComponent({
  name: 'InjectedFormulaInput',
  props: {
    modelValue: { type: Object, default: () => ({}) },
    allowedFormats: { type: Array, default: () => ['plain'] },
  },
  template: '<div />',
})

describe('NotificationWorkflowActionForm', () => {
  test('does not mark either content field as individually required', async () => {
    const wrapper = await mountSuspended(NotificationWorkflowActionForm, {
      global: {
        stubs: {
          FormGroup: FormGroupStub,
          InjectedFormulaInput: true,
        },
        mocks: {
          $t: (key) => key,
        },
      },
    })

    expect(wrapper.findAllComponents(FormGroupStub)).toHaveLength(2)
    expect(
      wrapper
        .findAllComponents(FormGroupStub)
        .map((formGroup) => formGroup.props('required'))
    ).toEqual([false, false])

    wrapper.unmount()
  })

  test('lets the title and description be formatted as markdown', async () => {
    const wrapper = await mountSuspended(NotificationWorkflowActionForm, {
      global: {
        stubs: {
          FormGroup: FormGroupStub,
          InjectedFormulaInput: InjectedFormulaInputStub,
        },
        mocks: {
          $t: (key) => key,
        },
      },
    })

    expect(
      wrapper
        .findAllComponents(InjectedFormulaInputStub)
        .map((input) => input.props('allowedFormats'))
    ).toEqual([
      ['plain', 'markdown'],
      ['plain', 'markdown'],
    ])

    wrapper.unmount()
  })
})
