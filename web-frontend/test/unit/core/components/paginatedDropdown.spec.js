import { defineComponent } from 'vue'

import PaginatedDropdown from '@baserow/modules/core/components/PaginatedDropdown'
import { TestApp } from '@baserow/test/helpers/testApp'
import flushPromises from 'flush-promises'

describe('PaginatedDropdown component', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(() => {
    testApp.afterEach()
  })

  const results = [
    { id: 1, value: 'Alpha' },
    { id: 2, value: '' },
  ]
  const fetchPage = () =>
    Promise.resolve({ data: { results, count: results.length } })

  const labelFn = (row) => (row.value === '' ? `Unnamed ${row.id}` : row.value)

  const mountComponent = (props = {}) =>
    testApp.mount(PaginatedDropdown, { props: { fetchPage, ...props } })

  test('valueName as a function renders the computed name per item', async () => {
    const wrapper = await mountComponent({ valueName: labelFn })
    await wrapper.vm.fetch(1, null)
    await flushPromises()
    expect(wrapper.text()).toContain('Alpha')
    expect(wrapper.text()).toContain('Unnamed 2')
  })

  test('valueName as a string still reads the property', async () => {
    const wrapper = await mountComponent({ valueName: 'value' })
    await wrapper.vm.fetch(1, null)
    await flushPromises()
    expect(wrapper.text()).toContain('Alpha')
  })

  test('exposes each result to a custom item component', async () => {
    const CustomResult = defineComponent({
      props: {
        result: { type: Object, required: true },
        name: { type: String, required: true },
        value: { type: Number, required: true },
      },
      template:
        '<li class="custom-result">{{ value }}:{{ name }}:{{ result.value }}</li>',
    })
    const wrapper = await testApp.mount(PaginatedDropdown, {
      props: {
        fetchPage,
        valueName: labelFn,
        resultItemComponent: CustomResult,
      },
    })
    await wrapper.vm.fetch(1, null)
    await flushPromises()

    expect(wrapper.findAll('.custom-result')).toHaveLength(2)
    expect(wrapper.findAll('.custom-result')[1].text()).toBe('2:Unnamed 2:')
  })

  test('uses idName to de-duplicate appended pages', async () => {
    const pagedFetch = (page) =>
      Promise.resolve({
        data: {
          results: [{ key: page, value: `Page ${page}` }],
          count: 2,
        },
      })
    const wrapper = await testApp.mount(PaginatedDropdown, {
      props: {
        fetchPage: pagedFetch,
        idName: 'key',
        valueName: 'value',
      },
    })

    await wrapper.vm.fetch(1, null)
    await wrapper.vm.fetch(2, null, false)
    await flushPromises()

    expect(wrapper.vm.results).toEqual([
      { key: 1, value: 'Page 1' },
      { key: 2, value: 'Page 2' },
    ])
  })

  test('select includes the resolved item when includeDisplayNameInSelectedEvent', async () => {
    const wrapper = await mountComponent({
      valueName: labelFn,
      includeDisplayNameInSelectedEvent: true,
    })
    await wrapper.vm.fetch(1, null)
    await flushPromises()

    wrapper.vm.select(2)

    const emitted = wrapper.emitted('input')
    expect(emitted[emitted.length - 1][0]).toEqual({
      value: 2,
      displayName: 'Unnamed 2',
      item: { id: 2, value: '' },
    })
  })
})
