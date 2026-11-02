import { nextTick } from 'vue'
import { flushPromises } from '@vue/test-utils'
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
afterEach(() => {
  testApp.afterEach()
  vi.restoreAllMocks()
})

describe('TextFilterWidget', () => {
  test('selects several values in place and clears to an empty list', async () => {
    const dropdown = {
      ...widget,
      mode: 'dropdown',
      multiple: true,
      default_value: '',
    }
    const store = testApp.store
    vi.spyOn(store.$client, 'get').mockResolvedValue({
      data: { results: ['France', 'Belgium'] },
    })
    await store.dispatch('dashboardApplication/forceSetWidgets', [dropdown])
    wrapper = await testApp.mount(TextFilterWidget, {
      props: { widget: dropdown },
    })
    await flushPromises()
    await wrapper.get('.dropdown__selected').trigger('click')
    for (const item of wrapper.findAll('.select__item-link'))
      await item.trigger('click')
    expect(store.getters['dashboardApplication/getWidgetValues'][1]).toEqual([
      'France',
      'Belgium',
    ])
    expect(wrapper.get('.dropdown__selected-text').text()).toBe(
      'France, Belgium'
    )
    expect(wrapper.get('.dropdown__items').classes()).not.toContain('hidden')
    expect(
      wrapper.findAll('.select__item-name-text').map((item) => item.text())
    ).toEqual(['France', 'Belgium'])
    await wrapper.get('.select__footer button').trigger('click')
    expect(store.getters['dashboardApplication/getWidgetValues'][1]).toEqual([])
    expect(wrapper.get('.dropdown__selected-placeholder').text()).toBe(
      'Type here'
    )
    store.commit('dashboardApplication/RESET')
  })
  test('loads public dropdown options when the formula is private', async () => {
    const dropdown = { ...widget, mode: 'dropdown', default_value: '' }
    const store = testApp.store
    const getOptions = vi.spyOn(store.$client, 'get').mockResolvedValue({
      data: { results: ['France'] },
    })
    await store.dispatch('dashboardApplication/forceSetWidgets', [dropdown])
    store.commit('dashboardApplication/SET_PUBLIC', {
      slug: 'shared',
      authToken: 'token',
    })
    wrapper = await testApp.mount(TextFilterWidget, {
      props: { widget: dropdown },
    })
    await flushPromises()
    expect(wrapper.get('.select__item-name-text').text()).toBe('France')
    expect(getOptions).toHaveBeenCalledWith(
      '/dashboard/public/shared/widgets/1/options/',
      {
        headers: { 'Baserow-Dashboard-Authorization': 'JWT token' },
      }
    )
    store.commit('dashboardApplication/RESET')
  })
  test('selects and clears dropdown values without changing option order or losing input text', async () => {
    const dropdown = {
      ...widget,
      mode: 'dropdown',
      options: { formula: 'France, Belgium, Morocco', mode: 'raw' },
      default_value: '',
    }
    const store = testApp.store
    const getOptions = vi.spyOn(store.$client, 'get').mockResolvedValue({
      data: { results: ['France', 'Belgium', 'Morocco'] },
    })
    await store.dispatch('dashboardApplication/forceSetWidgets', [dropdown])
    wrapper = await testApp.mount(TextFilterWidget, {
      props: { widget: dropdown },
    })
    await flushPromises()
    const names = () =>
      wrapper.findAll('.select__item-name-text').map((item) => item.text())
    expect(names()).toEqual(['France', 'Belgium', 'Morocco'])
    await wrapper.get('.dropdown__selected').trigger('click')
    await wrapper.findAll('.select__item-link')[1].trigger('click')
    expect(store.getters['dashboardApplication/getWidgetValues'][1]).toBe(
      'Belgium'
    )
    expect(wrapper.get('.dropdown__selected-text').text()).toBe('Belgium')
    expect(names()).toEqual(['France', 'Belgium', 'Morocco'])
    await wrapper.get('.dropdown__selected').trigger('click')
    await wrapper.get('.select__search-input').setValue('Fra')
    await wrapper.get('.select__search-input').trigger('keyup')
    expect(wrapper.findAll('.select__item.visible')).toHaveLength(1)
    expect(store.getters['dashboardApplication/getWidgetValues'][1]).toBe(
      'Belgium'
    )
    await wrapper.get('.select__footer button').trigger('click')
    expect(store.getters['dashboardApplication/getWidgetValues'][1]).toBe('')
    await wrapper.setProps({ widget: { ...dropdown, mode: 'input' } })
    await wrapper.get('input').setValue('Unlisted value')
    await wrapper.setProps({ widget: dropdown })
    expect(wrapper.get('.dropdown__selected-text').text()).toBe(
      'Unlisted value'
    )
    expect(getOptions).toHaveBeenCalledTimes(1)
    store.commit('dashboardApplication/RESET')
  })
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
