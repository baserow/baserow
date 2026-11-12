import { flushPromises } from '@vue/test-utils'
import { TestApp } from '@baserow/test/helpers/testApp'
import DashboardTableSelector from '@baserow/modules/dashboard/components/data_source/DashboardTableSelector'

let testApp
beforeEach(() => {
  testApp = new TestApp()
})
afterEach(async () => {
  await testApp.afterEach()
  vi.restoreAllMocks()
})
async function mountSelector({
  own = false,
  linked = false,
  disabled = false,
} = {}) {
  const store = testApp.store
  store.commit('dashboardApplication/SET_WIDGETS', [
    { id: 1, type: 'summary', data_source_id: 2 },
    {
      id: 3,
      type: 'text_filter',
      target_filters: linked
        ? [
            {
              target_widget_id: 1,
              enabled: !disabled,
              group: { filters: [] },
              alternative_group: { filters: [{ field: 4 }] },
            },
          ]
        : [],
    },
  ])
  return testApp.mount(DashboardTableSelector, {
    props: {
      modelValue: 10,
      dataSource: {
        id: 2,
        type: 'local_baserow_aggregate_rows',
        filters: own ? [{ field: 4 }] : [],
      },
      databases: [
        {
          id: 5,
          name: 'Sales',
          tables: [
            { id: 10, name: 'Orders 2026' },
            { id: 11, name: 'Orders 2027' },
          ],
        },
      ],
    },
  })
}
async function selectNext(wrapper) {
  await wrapper.find('.dropdown__selected').trigger('click')
  await wrapper
    .findAll('.select__item-link')
    .find((item) => item.text().includes('Orders 2027'))
    .trigger('click')
  await flushPromises()
}
const button = (wrapper, label) =>
  wrapper.findAll('button').find((item) => item.text() === label)

test.each([{ own: true }, { linked: true }, { linked: true, disabled: true }])(
  'asks before clearing conditions (%j) and cancel preserves the table',
  async (configuration) => {
    const wrapper = await mountSelector(configuration)
    await selectNext(wrapper)
    expect(wrapper.emitted('update:modelValue')).toBeUndefined()
    expect(wrapper.text()).toContain('dashboardTableSelector.confirmTitle')
    await button(wrapper, 'action.cancel').trigger('click')
    await vi.waitFor(() =>
      expect(wrapper.find('.modal__box').exists()).toBe(false)
    )
    expect(wrapper.emitted('update:modelValue')).toBeUndefined()
    expect(wrapper.find('.dropdown__selected').text()).toContain('Orders 2026')
    await selectNext(wrapper)
    await button(wrapper, 'dashboardTableSelector.confirmAction').trigger(
      'click'
    )
    expect(wrapper.emitted('update:modelValue')).toEqual([[11]])
  }
)

test('changes directly without conditions to clear', async () => {
  const wrapper = await mountSelector()
  await selectNext(wrapper)
  expect(wrapper.emitted('update:modelValue')).toEqual([[11]])
  await vi.waitFor(() =>
    expect(wrapper.find('.modal__box').exists()).toBe(false)
  )
})

test('dismisses a pending confirmation when another source is selected', async () => {
  const wrapper = await mountSelector({ own: true })
  await selectNext(wrapper)
  await wrapper.setProps({
    dataSource: { id: 99, type: 'local_baserow_aggregate_rows', filters: [] },
  })
  expect(wrapper.emitted('update:modelValue')).toBeUndefined()
  await vi.waitFor(() =>
    expect(wrapper.find('.modal__box').exists()).toBe(false)
  )
})
