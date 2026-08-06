import flushPromises from 'flush-promises'
import { TestApp } from '@baserow/test/helpers/testApp'
import DatabaseWorkflowActionWithService from '@baserow/modules/database/components/field/DatabaseWorkflowActionWithService'

const WORKSPACE = { id: 1 }
const OWN_DATABASE_ID = 100
const OTHER_DATABASE_ID = 101

// What `GET /database/fields/table/{id}/` returns, which is the same shape the
// service schema carries as each property's `metadata`.
const TABLE_FIELDS = [
  { id: 10, name: 'Name', type: 'text', read_only: false },
  { id: 11, name: 'Created on', type: 'created_on', read_only: true },
  { id: 12, name: 'Notes', type: 'long_text', read_only: false },
]

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

  const mountAction = async (type = 'create_row', service = {}) =>
    testApp.mount(DatabaseWorkflowActionWithService, {
      props: {
        workflowAction: { id: 1, type, service },
        database: { id: OWN_DATABASE_ID, workspace: WORKSPACE },
        defaultValues: { service },
      },
      global: {
        provide: { workspace: WORKSPACE },
      },
    })

  test('the service form gets the workspace databases', async () => {
    await seedApplications()

    const wrapper = await mountAction('create_row')

    const serviceForm = wrapper.findComponent({
      name: 'LocalBaserowUpsertRowServiceForm',
    })
    expect(serviceForm.exists()).toBe(true)

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

  test('an unsaved action still offers the target table field mappings', async () => {
    await seedApplications()
    testApp.mock.onGet('/database/fields/table/2/').reply(200, TABLE_FIELDS)

    // No schema, because nothing has been saved: the state a newly added
    // action is in. It used to make the form claim the table had no writable
    // fields, so no mapping could ever be configured before a save.
    const wrapper = await mountAction('create_row', { table_id: 2 })
    await flushPromises()

    const serviceForm = wrapper.findComponent({
      name: 'LocalBaserowUpsertRowServiceForm',
    })
    expect(serviceForm.props('mappableFields').map((f) => f.name)).toEqual([
      'Name',
      'Notes',
    ])
    expect(serviceForm.vm.writableSchemaFields.map((f) => f.name)).toEqual([
      'Name',
      'Notes',
    ])
    expect(wrapper.findComponent({ name: 'Alert' }).exists()).toBe(false)
  })

  test('update row gets its mappings too, through its wrapper form', async () => {
    await seedApplications()
    testApp.mock.onGet('/database/fields/table/2/').reply(200, TABLE_FIELDS)

    // Update row's form is a thin wrapper that forwards $attrs, so anything
    // deciding this from the form component itself gets it wrong here.
    const wrapper = await mountAction('update_row', { table_id: 2 })
    await flushPromises()

    expect(wrapper.vm.supportsFieldMappings).toBe(true)
    expect(
      wrapper
        .findComponent({ name: 'LocalBaserowUpsertRowServiceForm' })
        .props('mappableFields')
        .map((field) => field.name)
    ).toEqual(['Name', 'Notes'])
  })

  test('a read only field is not offered as a mapping', async () => {
    await seedApplications()
    testApp.mock.onGet('/database/fields/table/2/').reply(200, TABLE_FIELDS)

    const wrapper = await mountAction('create_row', { table_id: 2 })
    await flushPromises()

    const names = wrapper
      .findComponent({ name: 'LocalBaserowUpsertRowServiceForm' })
      .props('mappableFields')
      .map((field) => field.name)
    expect(names).not.toContain('Created on')
  })

  test('picking a different table replaces the mappings', async () => {
    await seedApplications()
    testApp.mock.onGet('/database/fields/table/1/').reply(200, TABLE_FIELDS)
    testApp.mock
      .onGet('/database/fields/table/2/')
      .reply(200, [{ id: 20, name: 'Company', type: 'text', read_only: false }])

    const wrapper = await mountAction('create_row', { table_id: 1 })
    await flushPromises()

    // A saved schema would still describe table 1 here, so the fetched list is
    // the only one that tells the truth about the newly picked table.
    await wrapper.setProps({ defaultValues: { service: { table_id: 2 } } })
    wrapper.vm.values.service = { table_id: 2 }
    await flushPromises()

    expect(
      wrapper
        .findComponent({ name: 'LocalBaserowUpsertRowServiceForm' })
        .props('mappableFields')
        .map((field) => field.name)
    ).toEqual(['Company'])
  })

  test('re-picking the table already selected keeps the mappings visible', async () => {
    await seedApplications()
    testApp.mock.onGet('/database/fields/table/2/').reply(200, TABLE_FIELDS)

    const wrapper = await mountAction('create_row', { table_id: 2 })
    await flushPromises()

    const serviceForm = wrapper.findComponent({
      name: 'LocalBaserowUpsertRowServiceForm',
    })
    expect(wrapper.findComponent({ name: 'FieldMappingsForm' }).exists()).toBe(
      true
    )

    // The table dropdown is not clearable, so choosing the table that is
    // already selected re-emits the same id. `table_id` never changes, so
    // nothing refetches and nothing toggles the `loading` prop.
    wrapper
      .findComponent({ name: 'LocalBaserowServiceForm' })
      .vm.$emit('table-changed', 2)
    await flushPromises()

    // The editor makes no round trip on a table change, so it must never raise
    // a spinner it has no way of lowering: that hides the mappings for good.
    expect(serviceForm.vm.tableLoading).toBe(false)
    expect(wrapper.findComponent({ name: 'FieldMappingsForm' }).exists()).toBe(
      true
    )
  })

  test('the spinner covers the fetch a real table change starts', async () => {
    await seedApplications()
    testApp.mock.onGet('/database/fields/table/1/').reply(200, TABLE_FIELDS)
    let releaseSecondFetch
    testApp.mock.onGet('/database/fields/table/2/').reply(
      () =>
        new Promise((resolve) => {
          releaseSecondFetch = () => resolve([200, TABLE_FIELDS])
        })
    )

    const wrapper = await mountAction('create_row', { table_id: 1 })
    await flushPromises()

    const serviceForm = wrapper.findComponent({
      name: 'LocalBaserowUpsertRowServiceForm',
    })
    expect(serviceForm.vm.tableLoading).toBe(false)

    wrapper.vm.values.service = { table_id: 2 }
    await flushPromises()

    // Held open: the old table's mappings must not sit there looking current
    // while the new table's are still in flight.
    expect(serviceForm.vm.tableLoading).toBe(true)
    expect(wrapper.findComponent({ name: 'FieldMappingsForm' }).exists()).toBe(
      false
    )

    releaseSecondFetch()
    await flushPromises()

    expect(serviceForm.vm.tableLoading).toBe(false)
    expect(wrapper.findComponent({ name: 'FieldMappingsForm' }).exists()).toBe(
      true
    )
  })

  test('a slow fetch overtaken by a newer one does not win', async () => {
    await seedApplications()
    // Table 1's response is held open so table 2's can overtake it, which is
    // what happens when the user picks two tables in quick succession.
    let releaseTableOne
    testApp.mock.onGet('/database/fields/table/1/').reply(
      () =>
        new Promise((resolve) => {
          releaseTableOne = () =>
            resolve([
              200,
              [{ id: 10, name: 'Stale', type: 'text', read_only: false }],
            ])
        })
    )
    testApp.mock
      .onGet('/database/fields/table/2/')
      .reply(200, [{ id: 20, name: 'Fresh', type: 'text', read_only: false }])

    const wrapper = await mountAction('create_row', {})

    wrapper.vm.values.service = { table_id: 1 }
    await wrapper.vm.$nextTick()
    wrapper.vm.values.service = { table_id: 2 }
    await flushPromises()

    expect(wrapper.vm.mappableFields.map((f) => f.name)).toEqual(['Fresh'])

    // Table 1 answers last. Its response describes a table nobody has
    // selected any more, so it must be discarded rather than applied.
    releaseTableOne()
    await flushPromises()

    expect(wrapper.vm.mappableFields.map((f) => f.name)).toEqual(['Fresh'])
    expect(wrapper.vm.fieldsLoading).toBe(false)
  })

  test('clearing the table lowers a spinner an in flight fetch raised', async () => {
    await seedApplications()
    let releaseTableOne
    testApp.mock.onGet('/database/fields/table/1/').reply(
      () =>
        new Promise((resolve) => {
          releaseTableOne = () => resolve([200, TABLE_FIELDS])
        })
    )

    const wrapper = await mountAction('create_row', {})

    wrapper.vm.values.service = { table_id: 1 }
    await flushPromises()
    expect(wrapper.vm.fieldsLoading).toBe(true)

    // Changing database clears the table while the fetch is still running.
    wrapper.vm.values.service = { table_id: null }
    await flushPromises()

    expect(wrapper.vm.fieldsLoading).toBe(false)
    expect(wrapper.vm.mappableFields).toBeNull()

    // The abandoned fetch answering must not re-raise or re-populate anything.
    releaseTableOne()
    await flushPromises()

    expect(wrapper.vm.fieldsLoading).toBe(false)
    expect(wrapper.vm.mappableFields).toBeNull()
  })

  test('the delete row action asks for no fields and takes neither prop', async () => {
    await seedApplications()

    const wrapper = await mountAction('delete_row', { table_id: 2 })
    await flushPromises()

    // Delete row has no field mappings, so fetching them would be a wasted
    // request and the props would land as stray attributes on its form.
    expect(testApp.mock.history.get).toHaveLength(0)
    expect(wrapper.vm.supportsFieldMappings).toBe(false)
    expect(wrapper.vm.mappableFields).toBeNull()
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
    expect(
      wrapper.findComponent({ name: 'LocalBaserowTableSelector' }).exists()
    ).toBe(true)
  })
})
