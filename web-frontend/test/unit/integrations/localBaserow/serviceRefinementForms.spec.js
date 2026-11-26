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
  const button = wrapper.find('.service-form__refinement-chip')
  expect(button.text()).toBe('serviceRefinementForms.filterTabTitle - 0')
  expect(button.classes()).not.toContain(
    'service-form__refinement-chip--active'
  )
  await button.trigger('click')
  const context = new DOMWrapper(document.body).find(
    '.service-form__context--filter'
  )
  expect(context.text()).toContain('serviceRefinementForms.noFiltersTitle')

  await context
    .findAll('button')
    .find(
      (action) =>
        action.text() === 'localBaserowTableServiceConditionalForm.addFilter'
    )
    .trigger('click')
  await flushPromises()
  expect(button.find('.service-form__refinement-count').text()).toBe('1')
  expect(button.classes()).toContain('service-form__refinement-chip--active')
  expect(context.findAll('.filters__item--level-1')).toHaveLength(1)

  await wrapper.setProps({ filterCountOverride: 3 })
  expect(button.find('.service-form__refinement-count').text()).toBe('3')
  expect(context.findAll('.filters__item--level-1')).toHaveLength(1)
  await wrapper.setProps({ filterCountOverride: null })
  expect(button.find('.service-form__refinement-count').text()).toBe('1')
})

test('shows the sort empty state only for the default sort form', async () => {
  const values = reactive({ table_id: 2, sortings: [] })
  const mountSort = async (slots = {}) => {
    const wrapper = await testApp.mount(ServiceRefinementForms, {
      props: {
        values,
        tableFields: [{ id: 7, name: 'Name', type: 'text' }],
        small: true,
        showSort: true,
      },
      slots,
      global: { stubs: { Teleport: false } },
    })
    await wrapper.find('.service-form__refinement-chip').trigger('click')
    return new DOMWrapper(document.body).find('.service-form__context--sort')
  }

  const defaultContext = await mountSort()
  expect(defaultContext.text()).toContain('serviceRefinementForms.noSortsTitle')
  testApp.afterEach()

  const customContext = await mountSort({
    'sort-form': '<div class="custom-sort-form">Sort by</div>',
  })
  expect(customContext.find('.custom-sort-form').exists()).toBe(true)
  expect(customContext.text()).not.toContain(
    'serviceRefinementForms.noSortsTitle'
  )
})
