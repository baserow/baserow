import { DOMWrapper, flushPromises } from '@vue/test-utils'
import { TestApp } from '@baserow/test/helpers/testApp'
import Dashboard from '@baserow/modules/dashboard/components/Dashboard'

let testApp
beforeEach(() => {
  testApp = new TestApp()
})
afterEach(() => testApp.afterEach())

async function render() {
  testApp.mock.onGet('/dashboard/1/widgets/').reply(200, [])
  testApp.mock.onGet('/dashboard/1/filters/').reply(200, [])
  testApp.mock.onGet('/dashboard/1/data-sources/').reply(200, [])
  await testApp.store.dispatch('dashboardApplication/fetchInitial', {
    dashboardId: 1,
    forEditing: false,
  })
  return testApp.mount(Dashboard, {
    props: {
      dashboard: {
        id: 1,
        name: 'Dashboard',
        description: '',
        workspace: { id: 1 },
      },
      loading: false,
    },
  })
}

test('creates a Text filter from the shared header menu and opens its settings', async () => {
  const wrapper = await render()
  const filter = {
    id: 5,
    dashboard_id: 1,
    label: 'Filter',
    type: 'text',
    operator: 'equal',
    mode: 'dropdown',
    multiple: false,
  }
  testApp.mock.onPost('/dashboard/1/filters/').reply(() => {
    testApp.mock.onGet('/dashboard/1/filters/').reply(200, [filter])
    return [200, filter]
  })
  await wrapper.get('header .dashboard-add-element__trigger').trigger('click')
  await flushPromises()
  const body = new DOMWrapper(document.body)
  const menu = body.get('.dashboard-add-element__context')
  expect(menu.text()).toContain('dashboardAddElement.widget')
  expect(menu.text()).toContain('dashboardAddElement.filter')
  await menu.get('[data-testid="create-dashboard-filter"]').trigger('click')
  await flushPromises()
  expect(testApp.mock.history.post).toHaveLength(1)
  expect(JSON.parse(testApp.mock.history.post[0].data)).toEqual({
    label: 'dashboardFilter.defaultLabel',
    type: 'text',
  })
  expect(wrapper.get('.dashboard-filter-settings input').element.value).toBe(
    'Filter'
  )
  expect(wrapper.get('header').text()).toContain('dashboardHeader.doneEditing')
  expect(wrapper.get('.dashboard-filters').text()).toContain('Filter')
  expect(wrapper.find('.dashboard-filters__add').exists()).toBe(false)
  expect(body.get('.dashboard-add-element__context').classes()).toContain(
    'visibility-hidden'
  )
})

test('disables the menu until creation finishes and allows retry after a failure', async () => {
  const wrapper = await render()
  let finishRequest
  testApp.dontFailOnErrorResponses()
  testApp.mock.onPost('/dashboard/1/filters/').reply(
    () =>
      new Promise((resolve) => {
        finishRequest = resolve
      })
  )
  await wrapper.get('.dashboard-add-element__trigger').trigger('click')
  await flushPromises()
  await testApp.body
    .get('[data-testid="create-dashboard-filter"]')
    .trigger('click')
  await flushPromises()
  expect(wrapper.get('.dashboard-add-element__trigger').element.disabled).toBe(
    true
  )
  expect(testApp.mock.history.post).toHaveLength(1)
  finishRequest([500, {}])
  await flushPromises()
  expect(wrapper.get('.dashboard-add-element__trigger').element.disabled).toBe(
    false
  )
  expect(wrapper.find('.dashboard-filter-settings').exists()).toBe(false)
  expect(wrapper.get('header').text()).not.toContain(
    'dashboardHeader.doneEditing'
  )
  await wrapper.get('.dashboard-add-element__trigger').trigger('click')
  await flushPromises()
  expect(
    testApp.body.get('.dashboard-add-element__context').classes()
  ).not.toContain('visibility-hidden')
})

test('does not enter edit mode on a new dashboard when creation finishes after navigation', async () => {
  const wrapper = await render()
  let finishRequest
  testApp.mock.onPost('/dashboard/1/filters/').reply(
    () =>
      new Promise((resolve) => {
        finishRequest = resolve
      })
  )
  await wrapper.get('.dashboard-add-element__trigger').trigger('click')
  await flushPromises()
  await testApp.body
    .get('[data-testid="create-dashboard-filter"]')
    .trigger('click')
  await flushPromises()
  testApp.mock.onGet('/dashboard/2/widgets/').reply(200, [])
  testApp.mock.onGet('/dashboard/2/filters/').reply(200, [])
  testApp.mock.onGet('/dashboard/2/data-sources/').reply(200, [])
  await testApp.store.dispatch('dashboardApplication/fetchInitial', {
    dashboardId: 2,
    forEditing: false,
  })
  await wrapper.setProps({
    dashboard: { id: 2, name: 'Other dashboard', workspace: { id: 1 } },
  })
  finishRequest([
    200,
    { id: 5, dashboard_id: 1, label: 'Filter', type: 'text' },
  ])
  await flushPromises()
  expect(wrapper.get('header').text()).toContain(
    'dashboardHeaderMenuItems.editMode'
  )
  expect(wrapper.get('header').text()).not.toContain(
    'dashboardHeader.doneEditing'
  )
  expect(wrapper.find('.dashboard-filter-settings').exists()).toBe(false)
  expect(wrapper.find('.dashboard-filters').exists()).toBe(false)
})
