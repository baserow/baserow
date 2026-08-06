import { TestApp } from '@baserow/test/helpers/testApp'
import WorkflowActionWithService from '@baserow/modules/builder/components/workflowAction/WorkflowActionWithService'

const INTEGRATION_ID = 11
const DATABASES = [
  { id: 100, name: 'Customers', tables: [{ id: 1, name: 'Contacts' }] },
]

describe('WorkflowActionWithService', () => {
  let testApp = null
  // The integration store pushes onto `integrations`, so each test gets its own.
  let builder = null

  beforeEach(() => {
    testApp = new TestApp()
    builder = { id: 1, integrations: [] }
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const seedIntegration = async () => {
    await testApp.store.dispatch('integration/forceCreate', {
      application: builder,
      integration: {
        id: INTEGRATION_ID,
        type: 'local_baserow',
        context_data: { databases: DATABASES },
      },
    })
  }

  const mountAction = async (type, service = {}) => {
    const workflowAction = { id: 1, type, service }
    return testApp.mount(WorkflowActionWithService, {
      props: { workflowAction, defaultValues: workflowAction },
      provide: { builder },
    })
  }

  test('a local baserow action offers an integration to pick', async () => {
    // The regression this guards: the shared service form used to carry the
    // dropdown, so removing it left the action with no way to choose one.
    await seedIntegration()

    const wrapper = await mountAction('create_row', {
      integration_id: INTEGRATION_ID,
    })

    expect(
      wrapper.findComponent({ name: 'IntegrationDropdown' }).exists()
    ).toBe(true)
  })

  test('the service form gets the chosen integration databases', async () => {
    await seedIntegration()

    const wrapper = await mountAction('create_row', {
      integration_id: INTEGRATION_ID,
    })

    expect(
      wrapper
        .findComponent({ name: 'LocalBaserowServiceForm' })
        .props('databases')
    ).toEqual(DATABASES)
  })

  test('without an integration there is nothing to pick a table from', async () => {
    await seedIntegration()

    const wrapper = await mountAction('create_row')

    expect(
      wrapper.findComponent({ name: 'LocalBaserowServiceForm' }).exists()
    ).toBe(false)
  })

  test('an action that picks no integration is left alone', async () => {
    // Core services offer their own dropdown, so this one must not add a second.
    await seedIntegration()

    const wrapper = await mountAction('http_request')

    expect(
      wrapper.findComponent({ name: 'IntegrationDropdown' }).exists()
    ).toBe(false)
  })
})
