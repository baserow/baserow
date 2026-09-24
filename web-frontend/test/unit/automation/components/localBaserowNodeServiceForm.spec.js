import { TestApp } from '@baserow/test/helpers/testApp'
import LocalBaserowNodeServiceForm from '@baserow/modules/automation/components/workflow/LocalBaserowNodeServiceForm'
import LocalBaserowUpsertRowServiceForm from '@baserow/modules/integrations/localBaserow/components/services/LocalBaserowUpsertRowServiceForm'

const INTEGRATION_ID = 7
const DATABASES = [
  { id: 100, name: 'Customers', tables: [{ id: 1, name: 'Contacts' }] },
]

const serviceType = {
  formComponent: LocalBaserowUpsertRowServiceForm,
  supportedTables: (tables) => tables,
}

describe('LocalBaserowNodeServiceForm', () => {
  let testApp = null
  // The store pushes onto `integrations`, so each test gets its own.
  let application = null

  beforeEach(() => {
    testApp = new TestApp()
    application = { id: 1, integrations: [] }
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const seedIntegration = async () => {
    await testApp.store.dispatch('integration/forceCreate', {
      application,
      integration: {
        id: INTEGRATION_ID,
        type: 'local_baserow',
        context_data: { databases: DATABASES },
      },
    })
  }

  const mountForm = async (defaultValues = {}) =>
    testApp.mount(LocalBaserowNodeServiceForm, {
      props: { application, serviceType, defaultValues },
    })

  test('the integration is chosen here rather than in the service form', async () => {
    await seedIntegration()

    const wrapper = await mountForm({ integration_id: INTEGRATION_ID })

    expect(
      wrapper.findComponent({ name: 'IntegrationDropdown' }).exists()
    ).toBe(true)
    expect(
      wrapper
        .findComponent({ name: 'LocalBaserowServiceForm' })
        .findComponent({ name: 'IntegrationDropdown' })
        .exists()
    ).toBe(false)
  })

  test('the service form gets the chosen integration databases', async () => {
    await seedIntegration()

    const wrapper = await mountForm({ integration_id: INTEGRATION_ID })

    expect(
      wrapper
        .findComponent({ name: 'LocalBaserowServiceForm' })
        .props('databases')
    ).toEqual(DATABASES)
  })

  test('without an integration there is nothing to pick a table from', async () => {
    await seedIntegration()

    const wrapper = await mountForm()

    // A table cannot be chosen before the integration that reaches it.
    expect(
      wrapper.findComponent({ name: 'LocalBaserowServiceForm' }).exists()
    ).toBe(false)
  })
})
