import { TEXT_FORMAT_TYPES } from '@baserow/modules/builder/enums'
import CheckboxElementForm from '@baserow/modules/builder/components/elements/components/forms/general/CheckboxElementForm'

import { mountSuspended } from '@nuxt/test-utils/runtime'
import { h } from 'vue'

describe('CheckboxElementForm', () => {
  let wrapper

  const defaultProps = {
    element: { id: 1, type: 'table', fields: [] },
    baseTheme: {},
    defaultValues: {
      label: { formula: 'Agree' },
      label_format: TEXT_FORMAT_TYPES.PLAIN,
      default_value: { formula: '' },
      required: false,
      styles: {},
      // Add some non-allowed properties
      someOtherProp: 'should not be included',
      anotherProp: 123,
    },
  }

  const mountComponent = (props = {}) => {
    return mountSuspended(CheckboxElementForm, {
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
      'label',
      'label_format',
      'default_value',
      'required',
      'styles',
    ])

    await wrapper.setData({
      values: {
        label_format: TEXT_FORMAT_TYPES.MARKDOWN,
      },
    })

    const emittedValues = wrapper.emitted('values-changed')
    expect(emittedValues).toBeTruthy()
    const lastEmittedValues = emittedValues[emittedValues.length - 1][0]

    expect(lastEmittedValues).toEqual({
      label: { formula: 'Agree' },
      label_format: TEXT_FORMAT_TYPES.MARKDOWN,
      default_value: { formula: '' },
      required: false,
      styles: {},
    })
    expect(lastEmittedValues.someOtherProp).toBeUndefined()
    expect(lastEmittedValues.anotherProp).toBeUndefined()
  })
})
