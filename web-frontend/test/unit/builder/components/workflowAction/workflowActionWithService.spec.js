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
      provide: { builder, workspace: { id: 1 } },
    })
  }

  test('a local baserow action offers an integration to pick', async () => {
    // The service form used to carry the dropdown, so removing it left the
    // action with no way to choose an integration.
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

  test('a freshly picked integration survives the form emitting', async () => {
    // The form only mounts once an integration is picked, and emits straight
    // away, so rebuilding the service from the server's copy dropped it.
    await seedIntegration()

    const wrapper = await mountAction('create_row')

    await wrapper
      .findComponent({ name: 'LocalBaserowIntegrationPicker' })
      .vm.$emit('update:modelValue', INTEGRATION_ID)
    await wrapper.vm.$nextTick()

    const serviceForm = wrapper.findComponent({
      name: 'LocalBaserowServiceForm',
    })
    await serviceForm.vm.$emit('values-changed', { table_id: 1 })
    await wrapper.vm.$nextTick()

    expect(wrapper.vm.values.service.integration_id).toBe(INTEGRATION_ID)
    expect(wrapper.vm.values.service.table_id).toBe(1)
  })

  test('a service change does not re-apply a stale schema after the server refreshes it', async () => {
    // Read-only backend fields (schema, context data, sample data) must always
    // come from the latest `workflowAction.service`. Buffering them re-injected
    // a stale schema on the next edit, which tore down and rebuilt the whole
    // field mapping list (a visible flicker).
    await seedIntegration()

    const schemaV1 = { type: 'object', properties: {} }
    const schemaV2 = {
      type: 'object',
      properties: { field_1: { metadata: { id: 1, name: 'Name' } } },
    }

    const wrapper = await mountAction('create_row', {
      integration_id: INTEGRATION_ID,
      table_id: 1,
      schema: schemaV1,
    })

    const serviceForm = wrapper.findComponent({
      name: 'LocalBaserowUpsertRowServiceForm',
    })

    // A first edit buffers the current (v1) service.
    await serviceForm.vm.$emit('values-changed', { field_mappings: [] })
    await wrapper.vm.$nextTick()
    expect(wrapper.vm.values.service.schema).toEqual(schemaV1)

    // The server responds and refreshes the action's service with a new schema.
    const refreshed = {
      id: 1,
      type: 'create_row',
      service: {
        integration_id: INTEGRATION_ID,
        table_id: 1,
        schema: schemaV2,
      },
    }
    await wrapper.setProps({
      workflowAction: refreshed,
      defaultValues: refreshed,
    })

    // A follow-up edit must carry the fresh schema, not the buffered stale one.
    await serviceForm.vm.$emit('values-changed', {
      field_mappings: [{ field_id: 1, enabled: true }],
    })
    await wrapper.vm.$nextTick()
    expect(wrapper.vm.values.service.schema).toEqual(schemaV2)
    // The editable change is still buffered.
    expect(wrapper.vm.values.service.field_mappings).toEqual([
      { field_id: 1, enabled: true },
    ])
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
