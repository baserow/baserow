import { TestApp } from '@baserow/test/helpers/testApp'
import { WidgetType } from '@baserow/modules/dashboard/widgetTypes'

class LifecycleWidgetType extends WidgetType {
  static getType() {
    return 'lifecycle_test'
  }
  get name() {
    return 'Lifecycle test'
  }
  afterCreate(widget, { commit }) {
    commit('SET_WIDGET_VALUE', { widgetId: widget.id, value: widget.title })
  }
  afterUpdate(widget, { commit }, previousWidget) {
    commit('SET_WIDGET_VALUE', {
      widgetId: widget.id,
      value: `${previousWidget.title} -> ${widget.title}`,
    })
  }
  afterDelete(widget, { commit }) {
    commit('DELETE_WIDGET_VALUE', widget.id)
  }
}

let testApp
beforeEach(() => {
  testApp = new TestApp()
  testApp.store.$registry.register('dashboardWidget', new LifecycleWidgetType())
})
afterEach(async () => {
  testApp.store.$registry.unregister(
    'dashboardWidget',
    LifecycleWidgetType.getType()
  )
  await testApp.afterEach()
})

test('registered widget hooks own local state across realtime and collection changes', async () => {
  const store = testApp.store
  store.commit('dashboardApplication/SET_DASHBOARD_ID', 42)
  const widget = {
    id: 1,
    type: 'lifecycle_test',
    title: 'One',
    dashboard_id: 42,
  }
  await store.dispatch('dashboardApplication/handleNewWidgetCreated', widget)
  expect(store.getters['dashboardApplication/getWidgetValues'][1]).toBe('One')
  await store.dispatch('dashboardApplication/forceSetWidgets', [
    { ...widget, title: 'Two' },
  ])
  expect(store.getters['dashboardApplication/getWidgetValues'][1]).toBe(
    'One -> Two'
  )
  await store.dispatch('dashboardApplication/handleWidgetUpdated', {
    ...widget,
    title: 'Three',
  })
  expect(store.getters['dashboardApplication/getWidgetValues'][1]).toBe(
    'Two -> Three'
  )
  store.commit('dashboardApplication/SELECT_WIDGET', 1)
  await store.dispatch('dashboardApplication/handleWidgetDeleted', 1)
  expect(store.getters['dashboardApplication/getWidgetValues']).toEqual({})
  expect(store.getters['dashboardApplication/getSelectedWidgetId']).toBe(null)
  await store.dispatch('dashboardApplication/forceCreateWidget', widget)
  expect(store.getters['dashboardApplication/getWidgetValues'][1]).toBe('One')
  await store.dispatch('dashboardApplication/forceSetWidgets', [])
  expect(store.getters['dashboardApplication/getWidgetValues']).toEqual({})
})
