import { TEXT_FORMAT_TYPES } from '@baserow/modules/builder/enums'
import { defineComponent, h } from 'vue'
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
  let wrapper

  const defaultProps = {
    element: { id: 1, type: 'table', fields: [] },
    baseTheme: {},
    defaultValues: {
      title: { formula: 'Saved' },
      title_format: TEXT_FORMAT_TYPES.PLAIN,
      description: { formula: 'Done' },
      description_format: TEXT_FORMAT_TYPES.PLAIN,
      // Add some non-allowed properties
      someOtherProp: 'should not be included',
      anotherProp: 123,
    },
  }

  const mountComponent = (props = {}) => {
    return mountSuspended(NotificationWorkflowActionForm, {
      props: {
        ...defaultProps,
        ...props,
      },
      mocks: {
        $t: (key) => key,
        $registry: {
          getOrderedList: () => [],
        },
      },
      global: {
        provide: {
          workspace: {},
          builder: {
            theme: {},
          },
          currentPage: {},
          elementPage: {},
          mode: 'edit',
          formulaComponent: () => h('div', `fake formula component`),
          dataProvidersAllowed: [],
          openCustomStyleForm: vi.fn(),
        },
      },
      stubs: {
        FormGroup: true,
        RadioGroup: true,
        InjectedFormulaInput: true,
        CustomStyle: true,
      },
    })
  }

  beforeEach(async () => {
    wrapper = await mountComponent()
  })

  afterEach(() => {
    wrapper.unmount()
  })

  test('only emits allowed values when values change', async () => {
    expect(wrapper.vm.allowedValues).toEqual([
      'title',
      'title_format',
      'description',
      'description_format',
    ])

    await wrapper.setData({
      values: {
        title_format: TEXT_FORMAT_TYPES.MARKDOWN,
        description_format: TEXT_FORMAT_TYPES.MARKDOWN,
      },
    })

    const emittedValues = wrapper.emitted('values-changed')
    expect(emittedValues).toBeTruthy()
    const lastEmittedValues = emittedValues[emittedValues.length - 1][0]

    expect(lastEmittedValues).toEqual({
      title: { formula: 'Saved' },
      title_format: TEXT_FORMAT_TYPES.MARKDOWN,
      description: { formula: 'Done' },
      description_format: TEXT_FORMAT_TYPES.MARKDOWN,
    })
    expect(lastEmittedValues.someOtherProp).toBeUndefined()
    expect(lastEmittedValues.anotherProp).toBeUndefined()
  })

  test('does not mark either content field as individually required', async () => {
    const wrapper = await mountSuspended(NotificationWorkflowActionForm, {
      global: {
        stubs: {
          FormGroup: FormGroupStub,
          InjectedFormulaInput: true,
          TextFormatSelector: true,
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
  })
})
