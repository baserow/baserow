import { TestApp } from '@baserow/test/helpers/testApp'
import DatabaseWorkflowActionWithService from '@baserow/modules/database/components/field/DatabaseWorkflowActionWithService'

const WORKSPACE = { id: 1 }
const OWN_DATABASE_ID = 100
const OTHER_DATABASE_ID = 101

describe('DatabaseWorkflowActionWithService', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const seedApplications = async () => {
    await testApp.store.dispatch('application/forceCreate', {
      id: OWN_DATABASE_ID,
      name: 'Customers',
      type: 'database',
      workspace: WORKSPACE,
      tables: [
        { id: 1, name: 'Contacts', database_id: OWN_DATABASE_ID },
        { id: 2, name: 'Companies', database_id: OWN_DATABASE_ID },
      ],
    })
    await testApp.store.dispatch('application/forceCreate', {
      id: OTHER_DATABASE_ID,
      name: 'Projects',
      type: 'database',
      workspace: WORKSPACE,
      tables: [{ id: 3, name: 'Tasks', database_id: OTHER_DATABASE_ID }],
    })
    // Not a database, so it must never show up as a table source.
    await testApp.store.dispatch('application/forceCreate', {
      id: 200,
      name: 'Site',
      type: 'builder',
      workspace: WORKSPACE,
      pages: [],
    })
    // A database in a different workspace, which must not leak in.
    await testApp.store.dispatch('application/forceCreate', {
      id: 300,
      name: 'Other workspace database',
      type: 'database',
      workspace: { id: 2 },
      tables: [{ id: 4, name: 'Elsewhere', database_id: 300 }],
    })
  }

  const mountAction = async (type = 'create_row') =>
    testApp.mount(DatabaseWorkflowActionWithService, {
      props: {
        workflowAction: { id: 1, type, service: {} },
        database: { id: OWN_DATABASE_ID, workspace: WORKSPACE },
        defaultValues: { service: {} },
      },
      global: {
        provide: { workspace: WORKSPACE },
      },
    })

  test('the service form gets the workspace databases and no integration picker', async () => {
    await seedApplications()

    const wrapper = await mountAction('create_row')

    const serviceForm = wrapper.findComponent({
      name: 'LocalBaserowUpsertRowServiceForm',
    })
    expect(serviceForm.exists()).toBe(true)
    expect(serviceForm.props('enableIntegrationPicker')).toBe(false)

    const databases = serviceForm.props('databases')
    expect(databases.length).toBeGreaterThan(0)
    // Derived from the store: only the workspace's database applications, the
    // field's own database included.
    expect(databases.map((database) => database.id).sort()).toEqual([
      OWN_DATABASE_ID,
      OTHER_DATABASE_ID,
    ])
    expect(databases.map((database) => database.name)).toContain('Customers')
    // Carries the tables the table selector needs.
    expect(
      databases.find((database) => database.id === OWN_DATABASE_ID).tables
    ).toHaveLength(2)
  })

  test('the table selector renders without an integration', async () => {
    await seedApplications()

    const wrapper = await mountAction('create_row')

    // The symptom browser verification caught: with no integration the table
    // selector was never rendered, so the action could not be configured.
    const selector = wrapper.findComponent({
      name: 'LocalBaserowTableSelector',
    })
    expect(selector.exists()).toBe(true)
    expect(selector.props('databases').map((d) => d.name)).toEqual([
      'Customers',
      'Projects',
    ])
    // No integration dropdown is offered, because a button field has none.
    expect(
      wrapper.findComponent({ name: 'IntegrationDropdown' }).exists()
    ).toBe(false)
  })

  test('the delete row action also gets the databases', async () => {
    await seedApplications()

    const wrapper = await mountAction('delete_row')

    const serviceForm = wrapper.findComponent({
      name: 'LocalBaserowServiceForm',
    })
    expect(
      serviceForm
        .props('databases')
        .map((d) => d.id)
        .sort()
    ).toEqual([OWN_DATABASE_ID, OTHER_DATABASE_ID])
    expect(serviceForm.props('enableIntegrationPicker')).toBe(false)
    expect(
      wrapper.findComponent({ name: 'LocalBaserowTableSelector' }).exists()
    ).toBe(true)
  })
})
