import { TEXT_FORMAT_TYPES } from '@baserow/modules/builder/enums'
import TextElementForm from '@baserow/modules/builder/components/elements/components/forms/general/TextElementForm'

import { mountSuspended } from '@nuxt/test-utils/runtime'
import { h } from 'vue'

// TODO MIG move that to builder folder

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
    return mountSuspended(TextElementForm, {
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
