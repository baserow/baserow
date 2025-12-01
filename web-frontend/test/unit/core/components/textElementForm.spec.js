import { mount } from '@vue/test-utils'
import { TEXT_FORMAT_TYPES } from '@baserow/modules/builder/enums'
import TextElementForm from '@baserow/modules/builder/components/elements/components/forms/general/TextElementForm'

describe('TextElementForm', () => {
  let wrapper

  const defaultProps = {
    defaultValues: {
      value: { formula: 'test text' },
      format: TEXT_FORMAT_TYPES.PLAIN,
      styles: {},
      // Add some non-allowed properties
      someOtherProp: 'should not be included',
      anotherProp: 123,
    },
  }

  const mountComponent = (props = {}) => {
    return mount(TextElementForm, {
      propsData: {
        ...defaultProps,
        ...props,
      },
      mocks: {
        $t: (key) => key,
        $registry: {
          getOrderedList: () => [],
        },
      },
      provide: {
        workspace: {},
        builder: {
          theme: {},
        },
        currentPage: {},
        elementPage: {},
        mode: 'edit',
      },
      stubs: {
        FormGroup: true,
        RadioGroup: true,
        InjectedFormulaInput: true,
        CustomStyle: true,
      },
    })
  }

  beforeEach(() => {
    wrapper = mountComponent()
  })

  afterEach(() => {
    wrapper.destroy()
  })

  test('only emits allowed values when values change', async () => {
    // Verify initial state
    expect(wrapper.vm.allowedValues).toEqual(['value', 'format', 'styles'])

    // Simulate value change
    await wrapper.setData({
      values: {
        format: TEXT_FORMAT_TYPES.MARKDOWN,
        styles: { color: 'red' },
      },
    })

    // Get the last emitted values-changed event
    const emittedValues = wrapper.emitted('values-changed')
    expect(emittedValues).toBeTruthy()
    const lastEmittedValues = emittedValues[emittedValues.length - 1][0]

    // Verify only allowed values are present
    expect(Object.keys(lastEmittedValues)).toEqual([
      'value',
      'format',
      'styles',
    ])
    expect(lastEmittedValues).toEqual({
      value: { formula: 'test text' },
      format: TEXT_FORMAT_TYPES.MARKDOWN,
      styles: { color: 'red' },
    })

    // Verify non-allowed values are not present
    expect(lastEmittedValues.someOtherProp).toBeUndefined()
    expect(lastEmittedValues.anotherProp).toBeUndefined()
  })
})
