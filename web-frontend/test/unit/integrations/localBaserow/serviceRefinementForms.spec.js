import { DOMWrapper, flushPromises } from '@vue/test-utils'
import { reactive } from 'vue'
import { TestApp } from '@baserow/test/helpers/testApp'
import ServiceRefinementForms from '@baserow/modules/integrations/localBaserow/components/services/ServiceRefinementForms'

let testApp
beforeEach(() => {
  testApp = new TestApp()
})
afterEach(() => testApp.afterEach())

test('keeps the default empty state and source count unless a caller supplies an override', async () => {
  const values = reactive({
    table_id: 2,
    filters: [],
    filter_groups: [],
    filter_type: 'AND',
  })
  const wrapper = await testApp.mount(ServiceRefinementForms, {
    props: {
      values,
      tableFields: [{ id: 7, name: 'Name', type: 'text' }],
      small: true,
      showFilter: true,
    },
    global: { stubs: { Teleport: false } },
  })
  const button = wrapper.find('.header__filter-link')
  expect(button.text()).toBe('serviceRefinementForms.filterTabTitle - 0')
  expect(button.classes()).not.toContain('active')
  await button.trigger('click')
  const context = new DOMWrapper(document.body).find(
    '.service-form__context--filter'
  )
  expect(context.text()).toContain(
    'localBaserowTableServiceConditionalForm.noFilterTitle'
  )

  await context
    .findAll('button')
    .find(
      (action) =>
        action.text() === 'localBaserowTableServiceConditionalForm.addFilter'
    )
    .trigger('click')
  await flushPromises()
  expect(button.text()).toBe('serviceRefinementForms.filterTabTitle - 1')
  expect(button.classes()).toContain('active')
  expect(context.findAll('.filters__item--level-1')).toHaveLength(1)

  await wrapper.setProps({ filterCountOverride: 3 })
  expect(button.text()).toBe('serviceRefinementForms.filterTabTitle - 3')
  expect(context.findAll('.filters__item--level-1')).toHaveLength(1)
  await wrapper.setProps({ filterCountOverride: null })
  expect(button.text()).toBe('serviceRefinementForms.filterTabTitle - 1')
})
