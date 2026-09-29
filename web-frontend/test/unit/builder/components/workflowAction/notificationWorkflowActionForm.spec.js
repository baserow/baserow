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
})
