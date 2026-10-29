import { nextTick } from 'vue'
import { TextFilterWidgetType } from '@baserow/modules/dashboard/widgetTypes'
import { mount } from '@vue/test-utils'
import { createStore } from 'vuex'
import dashboardApplication from '@baserow/modules/dashboard/store/dashboardApplication'
import TextFilterWidget from '@baserow/modules/dashboard/components/widget/TextFilterWidget'

let wrapper
const widget = {
  id: 1,
  type: 'text_filter',
  title: 'Search',
  placeholder: 'Type here',
  default_value: 'Initial',
}
afterEach(() => wrapper?.unmount())

describe('TextFilterWidget', () => {
  test('renders an accessible input and preserves viewer values across unrelated changes', async () => {
    const store = createStore({ modules: { dashboardApplication } })
    const widgetType = new TextFilterWidgetType({
      app: { $store: store, $i18n: { t: (key) => key } },
    })
    store.$registry = { get: () => widgetType }
    await store.dispatch('dashboardApplication/forceSetWidgets', [
      { ...widget },
    ])
    wrapper = mount(TextFilterWidget, {
      props: { widget: { ...widget } },
      global: { plugins: [store] },
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
