import flushPromises from 'flush-promises'

import { TestApp } from '@baserow/test/helpers/testApp'
import LocalBaserowSemanticSearchServiceForm from '@baserow_enterprise/integrations/localBaserow/components/services/LocalBaserowSemanticSearchServiceForm'
import { LocalBaserowSemanticSearchServiceType } from '@baserow_enterprise/integrations/localBaserow/serviceTypes'

describe('LocalBaserowSemanticSearchService', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
    testApp.store.commit('settings/SET_SETTINGS', {
      semantic_search: { available: true },
    })
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const mountForm = (defaultValues = {}, { small = false } = {}) =>
    testApp.mount(LocalBaserowSemanticSearchServiceForm, {
      props: {
        application: { id: 1 },
        serviceType: { supportedTables: (tables) => tables },
        defaultValues: { table_id: 1, integration_id: 1, ...defaultValues },
        small,
      },
    })

  test('the search settings are in the first tab, before the filters', async () => {
    testApp.mockServer.createFields({ id: 1 }, { id: 1 }, [
      { name: 'Document', type: 'long_text', semantic_search_enabled: true },
    ])

    const wrapper = await mountForm()
    await flushPromises()

    const tabTitles = wrapper.findAll('.tabs__item').map((tab) => tab.text())
    expect(tabTitles).toHaveLength(2)
    expect(tabTitles[0]).toContain('serviceRefinementForms.searchTabTitle')
    expect(tabTitles[1]).toContain('serviceRefinementForms.filterTabTitle')
    // The first tab is shown when the form opens.
    expect(wrapper.text()).toContain(
      'localBaserowSemanticSearchForm.searchQuery'
    )
  })

  test('a small form shows the search settings without a tab', async () => {
    testApp.mockServer.createFields({ id: 1 }, { id: 1 }, [
      { name: 'Document', type: 'long_text', semantic_search_enabled: true },
    ])

    const wrapper = await mountForm({}, { small: true })
    await flushPromises()

    expect(wrapper.findAll('.tabs__item')).toHaveLength(0)
    expect(wrapper.text()).toContain(
      'localBaserowSemanticSearchForm.searchQuery'
    )
  })

  test('only semantic search fields can be searched in', async () => {
    testApp.mockServer.createFields({ id: 1 }, { id: 1 }, [
      { name: 'Document', type: 'long_text', semantic_search_enabled: true },
      { name: 'Category', type: 'text', semantic_search_enabled: false },
    ])

    const wrapper = await mountForm()
    await flushPromises()

    const fieldNames = wrapper
      .findAllComponents({ name: 'DropdownItem' })
      .map((item) => item.props('name'))
    expect(fieldNames.filter((name) => name === 'Document')).toHaveLength(2)
    expect(fieldNames.filter((name) => name === 'Category')).toHaveLength(1)
    expect(wrapper.text()).not.toContain(
      'localBaserowSemanticSearchForm.noFields'
    )
    // No chosen fields means all of them are searched.
    expect(wrapper.text()).toContain(
      'localBaserowSemanticSearchForm.fieldsHelper'
    )
  })

  test("a chosen field that can't be searched anymore can be deselected", async () => {
    const [, category] = testApp.mockServer.createFields({ id: 1 }, { id: 1 }, [
      { name: 'Document', type: 'long_text', semantic_search_enabled: true },
      { name: 'Category', type: 'text', semantic_search_enabled: false },
    ])
    const wrapper = await mountForm({
      search_all_fields: false,
      search_field_ids: [category.id],
    })
    await flushPromises()

    const fieldsDropdown = wrapper
      .findAllComponents({ name: 'Dropdown' })
      .find((dropdown) => dropdown.props('modelValue')?.[0] === category.id)
    const options = fieldsDropdown
      .findAllComponents({ name: 'DropdownItem' })
      .map((item) => item.props('name'))
    expect(options).toEqual(['Document', 'Category'])
    expect(wrapper.text()).toContain(
      'localBaserowSemanticSearchForm.searchFieldsGone'
    )
  })

  test('warns when none of the chosen fields can be searched anymore', async () => {
    testApp.mockServer.createFields({ id: 1 }, { id: 1 }, [
      { name: 'Document', type: 'long_text', semantic_search_enabled: true },
    ])

    const wrapper = await mountForm({
      search_all_fields: false,
      search_field_ids: [],
    })
    await flushPromises()

    expect(wrapper.text()).toContain(
      'localBaserowSemanticSearchForm.searchFieldsGone'
    )
  })

  test("doesn't warn while clearing the chosen fields is being saved", async () => {
    const [field] = testApp.mockServer.createFields({ id: 1 }, { id: 1 }, [
      { name: 'Document', type: 'long_text', semantic_search_enabled: true },
    ])
    const saved = {
      search_all_fields: false,
      search_field_ids: [field.id],
      include_all_fields: false,
      included_field_ids: [field.id],
    }
    const wrapper = await mountForm(saved)
    await flushPromises()

    const dropdowns = wrapper
      .findAllComponents({ name: 'Dropdown' })
      .filter((dropdown) => dropdown.props('modelValue')?.[0] === field.id)
    expect(dropdowns).toHaveLength(2)
    dropdowns.forEach((dropdown) => dropdown.vm.$emit('update:modelValue', []))
    // The node shows the sent values before the server responds.
    await wrapper.setProps({
      defaultValues: {
        table_id: 1,
        integration_id: 1,
        ...saved,
        search_field_ids: [],
        included_field_ids: [],
      },
    })
    await flushPromises()

    expect(wrapper.vm.values.search_all_fields).toBe(true)
    expect(wrapper.vm.values.include_all_fields).toBe(true)
    expect(wrapper.text()).not.toContain(
      'localBaserowSemanticSearchForm.searchFieldsGone'
    )
    expect(wrapper.text()).not.toContain(
      'localBaserowSemanticSearchForm.includedFieldsGone'
    )
  })

  test('picking another table clears the chosen fields', async () => {
    const [field] = testApp.mockServer.createFields({ id: 1 }, { id: 1 }, [
      { name: 'Document', type: 'long_text', semantic_search_enabled: true },
    ])
    const wrapper = await mountForm({
      search_all_fields: false,
      search_field_ids: [field.id],
      include_all_fields: false,
      included_field_ids: [field.id],
    })
    await flushPromises()

    wrapper
      .findComponent({ name: 'LocalBaserowServiceForm' })
      .vm.$emit('table-changed', 2)
    await flushPromises()

    expect(wrapper.vm.values).toMatchObject({
      search_all_fields: true,
      search_field_ids: [],
      include_all_fields: true,
      included_field_ids: [],
    })
  })

  test('resetting to restored values keeps their fields', async () => {
    const [field] = testApp.mockServer.createFields({ id: 1 }, { id: 2 }, [
      { name: 'Document', type: 'long_text', semantic_search_enabled: true },
    ])
    const wrapper = await mountForm()
    await flushPromises()

    // Like after an undo, which restores another table and its fields.
    const restored = {
      table_id: 2,
      integration_id: 1,
      search_all_fields: false,
      search_field_ids: [field.id],
      include_all_fields: false,
      included_field_ids: [field.id],
    }
    await wrapper.setProps({ defaultValues: restored })
    await wrapper.vm.reset(true)
    await flushPromises()

    const { integration_id: integrationId, ...restoredValues } = restored
    expect(wrapper.vm.values).toMatchObject(restoredValues)
  })

  test('warns when none of the returned fields exist anymore', async () => {
    testApp.mockServer.createFields({ id: 1 }, { id: 1 }, [
      { name: 'Document', type: 'long_text', semantic_search_enabled: true },
    ])

    const wrapper = await mountForm({
      include_all_fields: false,
      included_field_ids: [],
    })
    await flushPromises()

    expect(wrapper.text()).toContain(
      'localBaserowSemanticSearchForm.includedFieldsGone'
    )
  })

  test('the maximum number of results is limited like on the server', async () => {
    testApp.store.commit('settings/SET_SETTINGS', {
      semantic_search: { available: true, max_results: 3 },
    })
    testApp.mockServer.createFields({ id: 1 }, { id: 1 }, [
      { name: 'Document', type: 'long_text', semantic_search_enabled: true },
    ])
    const wrapper = await mountForm()
    await flushPromises()

    wrapper.vm.v$.values.max_results.$model = 5
    await flushPromises()
    expect(wrapper.text()).toContain('error.maxValueField')

    wrapper.vm.v$.values.max_results.$model = 3
    await flushPromises()
    expect(wrapper.text()).not.toContain('error.maxValueField')
    expect(wrapper.text()).toContain(
      'localBaserowSemanticSearchForm.maxResultsHelper'
    )
  })

  test('explains how to enable semantic search without suitable fields', async () => {
    testApp.mockServer.createFields({ id: 1 }, { id: 1 }, [
      { name: 'Category', type: 'text', semantic_search_enabled: false },
    ])

    const wrapper = await mountForm()
    await flushPromises()

    expect(wrapper.text()).toContain(
      'localBaserowSemanticSearchForm.noFieldsTitle'
    )
    expect(wrapper.text()).toContain('localBaserowSemanticSearchForm.noFields')
    // The notice replaces the picker, which would have nothing to choose from.
    expect(wrapper.text()).not.toContain(
      'localBaserowSemanticSearchForm.fieldsHelper'
    )
  })

  test('is in error without a search query', () => {
    const serviceType = testApp
      .getRegistry()
      .get('service', LocalBaserowSemanticSearchServiceType.getType())
    const service = { table_id: 1, search_query: { formula: '' } }

    expect(serviceType.getErrorMessage({ service })).toBe(
      'serviceType.errorSearchQueryMissing'
    )
    expect(
      serviceType.getErrorMessage({
        service: { ...service, search_query: { formula: "'cake'" } },
      })
    ).toBe(null)
    // A missing table is reported first.
    expect(
      serviceType.getErrorMessage({ service: { ...service, table_id: null } })
    ).toBe('serviceType.errorNoTableSelected')
  })

  test('is deactivated without the license or the embeddings service', () => {
    const serviceType = testApp
      .getRegistry()
      .get('service', LocalBaserowSemanticSearchServiceType.getType())
    const workspace = { id: 1 }

    expect(serviceType.isDeactivatedReason({ workspace })).toBe(
      'enterprise.deactivated'
    )
    expect(serviceType.getDeactivatedClickModal({ workspace })).not.toBe(null)

    testApp.store.dispatch('auth/forceUpdateUserData', {
      active_licenses: { instance_wide: { advanced: true } },
    })
    expect(serviceType.isDeactivatedReason({ workspace })).toBe(null)

    testApp.store.commit('settings/SET_SETTINGS', {
      semantic_search: { available: false },
    })
    expect(serviceType.isDeactivatedReason({ workspace })).toBe(
      'serviceType.semanticSearchUnavailable'
    )
    // The paywall doesn't help if the instance doesn't support it.
    expect(serviceType.getDeactivatedClickModal({ workspace })).toBe(null)
  })
})
