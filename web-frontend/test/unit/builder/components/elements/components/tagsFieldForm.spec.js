import { TEXT_FORMAT_TYPES } from '@baserow/modules/builder/enums'
import TagsFieldForm from '@baserow/modules/builder/components/elements/components/collectionField/form/TagsFieldForm'

import { mountSuspended } from '@nuxt/test-utils/runtime'
import { h } from 'vue'

describe('TagsFieldForm', () => {
  let wrapper

  const defaultProps = {
    element: { id: 1, type: 'table', fields: [] },
    baseTheme: {},
    defaultValues: {
      values: { formula: 'a,b' },
      colors: { formula: '#acc8f8', mode: 'raw' },
      colors_is_formula: false,
      format: TEXT_FORMAT_TYPES.PLAIN,
      styles: {},
      // Add some non-allowed properties
      someOtherProp: 'should not be included',
      anotherProp: 123,
    },
  }

  const mountComponent = (props = {}) => {
    return mountSuspended(TagsFieldForm, {
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
      'values',
      'colors',
      'colors_is_formula',
      'format',
      'styles',
    ])

    await wrapper.setData({
      values: {
        format: TEXT_FORMAT_TYPES.MARKDOWN,
      },
    })

    const emittedValues = wrapper.emitted('values-changed')
    expect(emittedValues).toBeTruthy()
    const lastEmittedValues = emittedValues[emittedValues.length - 1][0]

    expect(lastEmittedValues).toEqual({
      values: { formula: 'a,b' },
      colors: { formula: '#acc8f8', mode: 'raw' },
      colors_is_formula: false,
      format: TEXT_FORMAT_TYPES.MARKDOWN,
      styles: {},
    })
    expect(lastEmittedValues.someOtherProp).toBeUndefined()
    expect(lastEmittedValues.anotherProp).toBeUndefined()
  })
})
