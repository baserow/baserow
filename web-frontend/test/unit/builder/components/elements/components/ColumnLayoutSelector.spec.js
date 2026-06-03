import ColumnLayoutSelector from '@baserow/modules/builder/components/elements/components/forms/general/ColumnLayoutSelector'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import { expect, test, describe, beforeEach, afterEach } from 'vitest'

describe('ColumnLayoutSelector', () => {
  let wrapper

  const defaultProps = {
    modelValue: 'auto',
    columnAmount: 1,
  }

  const mountComponent = (props = {}) => {
    return mountSuspended(ColumnLayoutSelector, {
      props: {
        ...defaultProps,
        ...props,
      },
      mocks: {
        $t: (key) => key,
      },
      stubs: {
        Dropdown: true,
        DropdownItem: true,
      },
    })
  }

  beforeEach(async () => {
    wrapper = await mountComponent()
  })

  afterEach(() => {
    wrapper.unmount()
  })

  test('displays no options when columnAmount is 1 or greater than 3', async () => {
    // columnAmount = 1
    let options = wrapper.findAll('.column-layout-selector__option')
    expect(options.length).toBe(0)

    for (const columnAmount of [4, 5, 6]) {
      await wrapper.setProps({ columnAmount })
      options = wrapper.findAll('.column-layout-selector__option')
      expect(options.length).toBe(0)
    }
  })

  test('displays variants when columnAmount is 2 or 3', async () => {
    await wrapper.setProps({ columnAmount: 2 })
    let options = wrapper.findAll('.column-layout-selector__option')
    expect(options.length).toBe(6) // 1:1, 1:2, 2:1, 1:3, 3:1, custom

    await wrapper.setProps({ columnAmount: 3 })
    options = wrapper.findAll('.column-layout-selector__option')
    expect(options.length).toBe(5) // 1:1:1, 1:1:2, 2:1:1, 1:2:1, custom
  })

  test('emits update events when column count changes', async () => {
    await wrapper.vm.onColumnCountChange(3)

    expect(wrapper.emitted('update:modelValue')).toBeTruthy()
    expect(wrapper.emitted('update:modelValue')[0]).toEqual(['auto'])

    expect(wrapper.emitted('update-amount')).toBeTruthy()
    expect(wrapper.emitted('update-amount')[0]).toEqual([3])
  })

  test('emits custom layout when column count is greater than 3', async () => {
    await wrapper.vm.onColumnCountChange(4)

    expect(wrapper.emitted('update:modelValue')).toBeTruthy()
    expect(wrapper.emitted('update:modelValue')[0]).toEqual(['custom'])

    expect(wrapper.emitted('update-amount')).toBeTruthy()
    expect(wrapper.emitted('update-amount')[0]).toEqual([4])
  })

  test('emits update events when a variant is selected', async () => {
    await wrapper.setProps({ columnAmount: 2 })
    await wrapper.vm.selectLayout({ value: '1:2', amount: 2 })

    expect(wrapper.emitted('update:modelValue')).toBeTruthy()
    expect(wrapper.emitted('update:modelValue')[0]).toEqual(['1:2'])

    expect(wrapper.emitted('update-amount')).toBeTruthy()
    expect(wrapper.emitted('update-amount')[0]).toEqual([2])
  })
})
