import { nextTick } from 'vue'
import { TestApp } from '@baserow/test/helpers/testApp'
import TextFilterWidget from '@baserow/modules/dashboard/components/widget/TextFilterWidget'

let wrapper, testApp
const widget = {
  id: 1,
  type: 'text_filter',
  title: 'Search',
  placeholder: 'Type here',
  default_value: 'Initial',
}
beforeEach(() => {
  testApp = new TestApp()
})
afterEach(() => testApp.afterEach())

describe('TextFilterWidget', () => {
  test('renders an accessible input and preserves viewer values across unrelated changes', async () => {
    const store = testApp.store
    await store.dispatch('dashboardApplication/forceSetWidgets', [
      { ...widget },
    ])
    wrapper = await testApp.mount(TextFilterWidget, {
      props: { widget: { ...widget } },
    })
    expect(wrapper.html()).toMatchSnapshot()
    const input = wrapper.get('input')
    expect(input.element.value).toBe('Initial')
    await input.setValue('Viewer text')
    expect(store.getters['dashboardApplication/getWidgetValues'][1]).toBe(
      'Viewer text'
    )
    await store.dispatch('dashboardApplication/forceUpdateWidget', {
      widgetId: 1,
      values: { title: 'Renamed' },
    })
    await wrapper.setProps({ widget: { ...widget, title: 'Renamed' } })
    expect(input.element.value).toBe('Viewer text')
    await input.setValue('')
    expect(input.element.value).toBe('')
    await store.dispatch('dashboardApplication/forceUpdateWidget', {
      widgetId: 1,
      values: { default_value: 'New default' },
    })
    await nextTick()
    expect(input.element.value).toBe('New default')
    store.commit('dashboardApplication/RESET')
  })
})
