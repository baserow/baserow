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

  const mountForm = (defaultValues = {}) =>
    testApp.mount(LocalBaserowSemanticSearchServiceForm, {
      props: {
        application: { id: 1 },
        serviceType: { supportedTables: (tables) => tables },
        defaultValues: { table_id: 1, integration_id: 1, ...defaultValues },
      },
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

  test('explains how to enable semantic search without suitable fields', async () => {
    testApp.mockServer.createFields({ id: 1 }, { id: 1 }, [
      { name: 'Category', type: 'text', semantic_search_enabled: false },
    ])

    const wrapper = await mountForm()
    await flushPromises()

    expect(wrapper.text()).toContain('localBaserowSemanticSearchForm.noFields')
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
