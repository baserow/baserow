import { h, nextTick, ref } from 'vue'
import { DOMWrapper } from '@vue/test-utils'
import { TestApp } from '@baserow/test/helpers/testApp'
import ABDropdown from '@baserow/modules/builder/components/elements/baseComponents/ABDropdown.vue'
import ABDropdownItem from '@baserow/modules/builder/components/elements/baseComponents/ABDropdownItem.vue'

describe('ABDropdown search', () => {
  let testApp

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const mountDropdown = (options, props = {}) =>
    testApp.mount(ABDropdown, {
      props: { showSearch: true, modelValue: 'alpha', ...props },
      slots: {
        default: () => options.value.map((option) => h(ABDropdownItem, option)),
      },
    })

  const search = async (wrapper, query) => {
    const input = wrapper.get('.select__search-input')
    await input.setValue(query)
    await input.trigger('keyup')
  }

  test.each([
    ['single', false, 'alpha'],
    ['multiple', true, ['alpha', 'beta']],
  ])(
    'Enter cannot select a stale focus with no results in %s selection',
    async (_mode, multiple, modelValue) => {
      const wrapper = await mountDropdown(
        ref([
          { key: 'alpha', value: 'alpha', name: 'Alpha' },
          { key: 'beta', value: 'beta', name: 'Beta' },
        ]),
        { multiple, modelValue }
      )
      const body = new DOMWrapper(document.body)

      await wrapper.get('.ab-dropdown__selected').trigger('click')
      await search(wrapper, 'beta')
      await body.trigger('keydown', { key: 'ArrowDown' })
      expect(
        wrapper.get('.ab-dropdownitem__item:not(.hidden)').classes()
      ).toContain('hover')
      await search(wrapper, 'no match')
      expect(wrapper.get('.select__items--empty').isVisible()).toBe(true)

      await body.trigger('keydown', { key: 'Enter' })

      expect(wrapper.emitted('update:modelValue')).toBeUndefined()
      expect(wrapper.get('.ab-dropdown__items').classes()).not.toContain(
        'hidden'
      )
    }
  )

  test('Enter ignores a filtered focus even when another result remains', async () => {
    const wrapper = await mountDropdown(
      ref([
        { key: 'alpha', value: 'alpha', name: 'Alpha' },
        { key: 'beta', value: 'beta', name: 'Beta' },
      ])
    )
    const body = new DOMWrapper(document.body)
    await wrapper.get('.ab-dropdown__selected').trigger('click')
    await search(wrapper, 'beta')
    await body.trigger('keydown', { key: 'ArrowDown' })
    await search(wrapper, 'alpha')

    await body.trigger('keydown', { key: 'Enter' })
    expect(wrapper.emitted('update:modelValue')).toBeUndefined()

    await body.trigger('keydown', { key: 'ArrowDown' })
    await body.trigger('keydown', { key: 'Enter' })
    expect(wrapper.emitted('update:modelValue')).toEqual([['alpha']])
  })

  test('new options inherit the current filter and replace the empty state', async () => {
    const options = ref([{ key: 'alpha', value: 'alpha', name: 'Alpha' }])
    const wrapper = await mountDropdown(options)
    await wrapper.get('.ab-dropdown__selected').trigger('click')
    await search(wrapper, 'beta')
    expect(wrapper.get('.select__items--empty').isVisible()).toBe(true)

    options.value = [
      { key: 'beta', value: 'beta', name: 'Beta' },
      { key: 'gamma', value: 'gamma', name: 'Gamma' },
    ]
    await nextTick()
    await nextTick()

    expect(wrapper.get('.select__items').isVisible()).toBe(true)
    expect(wrapper.find('.select__items--empty').exists()).toBe(false)
    const items = wrapper.findAll('.ab-dropdownitem__item')
    expect(items[0].classes()).not.toContain('hidden')
    expect(items[1].classes()).toContain('hidden')
  })

  test('changing an option label updates the results and empty state', async () => {
    const options = ref([{ key: 'alpha', value: 'alpha', name: 'Alpha' }])
    const wrapper = await mountDropdown(options)
    await wrapper.get('.ab-dropdown__selected').trigger('click')
    await search(wrapper, 'beta')
    expect(wrapper.get('.select__items--empty').isVisible()).toBe(true)

    options.value[0].name = 'Beta'
    await nextTick()

    expect(wrapper.get('.ab-dropdownitem__item-name-text').text()).toBe('Beta')
    expect(wrapper.get('.ab-dropdownitem__item').classes()).not.toContain(
      'hidden'
    )
    expect(wrapper.get('.select__items').isVisible()).toBe(true)
    expect(wrapper.find('.select__items--empty').exists()).toBe(false)

    options.value[0].name = 'Gamma'
    await nextTick()

    expect(wrapper.get('.ab-dropdownitem__item').classes()).toContain('hidden')
    expect(wrapper.get('.select__items').isVisible()).toBe(false)
    expect(wrapper.get('.select__items--empty').isVisible()).toBe(true)
  })

  test.each(['removed', 'disabled', 'hidden'])(
    'Enter ignores a focused option that becomes %s',
    async (state) => {
      const options = ref([
        { key: 'alpha', value: 'alpha', name: 'Alpha' },
        { key: 'beta', value: 'beta', name: 'Beta' },
      ])
      const wrapper = await mountDropdown(options)
      const body = new DOMWrapper(document.body)
      await wrapper.get('.ab-dropdown__selected').trigger('click')
      await search(wrapper, 'beta')
      await body.trigger('keydown', { key: 'ArrowDown' })

      if (state === 'removed') {
        options.value.pop()
      } else if (state === 'disabled') {
        options.value[1].disabled = true
      } else {
        options.value[1].visible = false
      }
      await nextTick()
      await nextTick()

      await body.trigger('keydown', { key: 'Enter' })

      expect(wrapper.emitted('update:modelValue')).toBeUndefined()
      expect(wrapper.get('.ab-dropdown__items').classes()).not.toContain(
        'hidden'
      )
      if (state !== 'disabled') {
        expect(wrapper.get('.select__items--empty').isVisible()).toBe(true)
      }
    }
  )

  test('emits remote queries and leaves the current results visible', async () => {
    const wrapper = await testApp.mount(ABDropdown, {
      props: { emitSearch: true, showSearch: true },
      slots: {
        default: () =>
          h(ABDropdownItem, { value: '1', name: 'Current result' }),
      },
    })

    await wrapper.get('.ab-dropdown__selected').trigger('click')
    await wrapper.get('.select__search-input').setValue('not currently loaded')
    await wrapper.get('.select__search-input').trigger('keyup')

    expect(wrapper.emitted('query-change')).toEqual([['not currently loaded']])
    expect(wrapper.get('.ab-dropdownitem__item').classes()).not.toContain(
      'hidden'
    )
    expect(wrapper.get('.select__items').isVisible()).toBe(true)
    expect(wrapper.find('.select__items--empty').exists()).toBe(false)

    const body = new DOMWrapper(document.body)
    await body.trigger('keydown', { key: 'ArrowDown' })
    await body.trigger('keydown', { key: 'Enter' })

    expect(wrapper.emitted('update:modelValue')).toEqual([['1']])
  })

  test('keeps the remote empty-state slot visible when there are no results', async () => {
    const wrapper = await testApp.mount(ABDropdown, {
      props: { emitSearch: true, showSearch: true },
      slots: { emptyState: '<span>No remote records</span>' },
    })

    await wrapper.get('.ab-dropdown__selected').trigger('click')
    await wrapper.get('.select__search-input').setValue('missing')
    await wrapper.get('.select__search-input').trigger('keyup')

    expect(wrapper.emitted('query-change')).toEqual([['missing']])
    expect(wrapper.get('.select__items--empty').text()).toBe(
      'No remote records'
    )
    expect(wrapper.get('.select__items').isVisible()).toBe(false)
  })
})
