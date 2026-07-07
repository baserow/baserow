import { VERTICAL_ALIGNMENTS } from '@baserow/modules/builder/enums'
import ColumnElementForm from '@baserow/modules/builder/components/elements/components/forms/general/ColumnElementForm'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import { expect, test, describe, beforeEach, afterEach, vi } from 'vitest'

describe('ColumnElementForm', () => {
  let wrapper

  const defaultProps = {
    defaultValues: {
      column_amount: 1,
      column_gap: 30,
      alignment: VERTICAL_ALIGNMENTS.TOP,
      layout_type: 'auto',
      column_weights: [1],
      column_stacking: {
        smartphone: 'stacked',
        tablet: 'horizontal',
        desktop: 'horizontal',
      },
      styles: {},
      someOtherProp: 'should not be included',
    },
  }

  const mountComponent = (props = {}) => {
    return mountSuspended(ColumnElementForm, {
      props: {
        ...defaultProps,
        ...props,
      },
      mocks: {
        $t: (key) => key,
      },
      global: {
        provide: {
          workspace: {},
          builder: { theme: {} },
          currentPage: {},
          elementPage: {},
          mode: 'edit',
        },
      },
      stubs: {
        FormGroup: true,
        FormInput: true,
        ColumnLayoutSelector: true,
        VerticalAlignmentSelector: true,
      },
    })
  }

  beforeEach(async () => {
    wrapper = await mountComponent()
  })

  afterEach(() => {
    wrapper.unmount()
  })

  test('only emits allowed values', async () => {
    expect(wrapper.vm.allowedValues).toEqual([
      'column_amount',
      'column_gap',
      'alignment',
      'layout_type',
      'column_weights',
      'column_stacking',
      'styles',
    ])

    await wrapper.setData({
      values: {
        column_amount: 1,
        column_gap: 20,
        alignment: VERTICAL_ALIGNMENTS.CENTER,
        layout_type: 'auto',
        column_weights: [1],
        column_stacking: {
          smartphone: 'stacked',
          tablet: 'horizontal',
          desktop: 'horizontal',
        },
        styles: {},
      },
    })

    const emittedValues = wrapper.emitted('values-changed')
    expect(emittedValues).toBeTruthy()
    const lastEmittedValues = emittedValues[emittedValues.length - 1][0]

    expect(Object.keys(lastEmittedValues).sort()).toEqual([
      'alignment',
      'column_amount',
      'column_gap',
      'column_stacking',
      'column_weights',
      'layout_type',
      'styles',
    ])
    expect(lastEmittedValues.someOtherProp).toBeUndefined()
  })

  test('updateColumnAmount correctly resizes column_weights', async () => {
    // Start with 1 column
    expect(wrapper.vm.values.column_weights).toEqual([1])

    // Change to 3 columns
    await wrapper.vm.updateColumnAmount(3)

    expect(wrapper.vm.values.column_amount).toBe(3)
    expect(wrapper.vm.values.column_weights).toEqual([1, 1, 1])

    // Change to 2 columns
    wrapper.vm.values.column_weights = [2, 3, 4]
    await wrapper.vm.updateColumnAmount(2)

    expect(wrapper.vm.values.column_amount).toBe(2)
    // Should preserve existing weights up to the new amount
    expect(wrapper.vm.values.column_weights).toEqual([2, 3])

    await wrapper.vm.updateColumnAmount(4)

    expect(wrapper.vm.values.column_amount).toBe(4)
    expect(wrapper.vm.values.layout_type).toBe('custom')
    expect(wrapper.vm.values.column_weights).toEqual([2, 3, 1, 1])
  })

  test('custom layout initializes equal weights and allows zero', async () => {
    wrapper.unmount()
    wrapper = await mountComponent({
      defaultValues: {
        ...defaultProps.defaultValues,
        column_amount: 3,
        layout_type: 'custom',
        column_weights: [1, 1, 1],
      },
    })

    expect(wrapper.html()).toContain('columnElementForm.customWeightsHelper')

    expect(wrapper.vm.custom_weights).toEqual([1, 1, 1])
    expect(wrapper.vm.values.column_weights).toEqual([1, 1, 1])

    wrapper.vm.onCustomWeightChange(1, 0)
    expect(wrapper.vm.custom_weights).toEqual([1, 0, 1])
    expect(wrapper.vm.values.column_weights).toEqual([1, 0, 1])

    expect(wrapper.vm.v$.custom_weights.$invalid).toBe(false)
  })

  test('custom weight inputs prevent text characters', () => {
    const preventTextInput = vi.fn()
    wrapper.vm.onCustomWeightKeydown({
      key: 'e',
      preventDefault: preventTextInput,
    })
    expect(preventTextInput).toHaveBeenCalledOnce()

    const preventDigitInput = vi.fn()
    wrapper.vm.onCustomWeightKeydown({
      key: '2',
      preventDefault: preventDigitInput,
    })
    expect(preventDigitInput).not.toHaveBeenCalled()

    const preventShortcut = vi.fn()
    wrapper.vm.onCustomWeightKeydown({
      key: 'a',
      metaKey: true,
      preventDefault: preventShortcut,
    })
    expect(preventShortcut).not.toHaveBeenCalled()

    const preventSecondDecimalSeparator = vi.fn()
    wrapper.vm.onCustomWeightKeydown({
      key: '.',
      currentTarget: { value: '1.5' },
      preventDefault: preventSecondDecimalSeparator,
    })
    expect(preventSecondDecimalSeparator).toHaveBeenCalledOnce()
  })

  test('layouts with more than 3 columns use custom weights directly', async () => {
    wrapper.unmount()
    wrapper = await mountComponent({
      defaultValues: {
        ...defaultProps.defaultValues,
        column_amount: 4,
        layout_type: 'auto',
        column_weights: [2, 0, 1, 3],
      },
    })

    expect(wrapper.vm.values.layout_type).toBe('custom')
    expect(wrapper.find('.column-layout-selector').exists()).toBe(false)
    expect(wrapper.html()).toContain('columnElementForm.customWeightsHelper')
    expect(wrapper.vm.custom_weights).toEqual([2, 0, 1, 3])
    expect(wrapper.vm.values.column_weights).toEqual([2, 0, 1, 3])
  })

  test('displays stacking options per device type', () => {
    expect(wrapper.html()).toContain('columnElementForm.columnStackingTitle')
    expect(wrapper.html()).toContain(
      'columnElementForm.columnStackingHorizontal'
    )
    expect(wrapper.html()).toContain('columnElementForm.columnStackingStacked')
  })

  test('uses stacked columns by default on smartphone', async () => {
    wrapper.unmount()
    const defaultValues = { ...defaultProps.defaultValues }
    delete defaultValues.column_stacking

    wrapper = await mountComponent({ defaultValues })

    expect(wrapper.vm.values.column_stacking).toEqual({
      smartphone: 'stacked',
      tablet: 'horizontal',
      desktop: 'horizontal',
    })
  })
})
