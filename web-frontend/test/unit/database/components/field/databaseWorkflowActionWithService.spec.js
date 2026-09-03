import { vi } from 'vitest'
import flushPromises from 'flush-promises'
import { readFileSync } from 'fs'
import { resolve } from 'path'
import { TestApp } from '@baserow/test/helpers/testApp'
import DatabaseWorkflowActionWithService from '@baserow/modules/database/components/field/DatabaseWorkflowActionWithService'
import { FIELDS_UNAVAILABLE } from '@baserow/modules/database/utils/buttonField'

// Read rather than imported: the i18n loader turns an imported locale file
// into compiled message ASTs, which the copy below can't be read off of.
const en = JSON.parse(
  readFileSync(
    resolve(process.cwd(), 'modules/database/locales/en.json'),
    'utf8'
  )
)

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

  const mountAction = async (
    type = 'local_baserow_create_row',
    service = {},
    database = { id: OWN_DATABASE_ID, workspace: WORKSPACE }
  ) =>
    testApp.mount(DatabaseWorkflowActionWithService, {
      props: {
        workflowAction: { id: 1, type, service },
        database,
        defaultValues: { service },
      },
      global: {
        provide: { workspace: WORKSPACE },
      },
    })

  test('a slack action fetches the bots of its database and offers them', async () => {
    await seedApplications()
    testApp.mock
      .onGet(`application/${OWN_DATABASE_ID}/integrations/`)
      .reply(200, [{ id: 7, type: 'slack_bot', name: 'Bot', order: '1' }])

    // The store's own object, as the table page hands it down, so the list
    // the fetch fills is the one the form reads.
    const database = testApp.store.getters['application/get'](OWN_DATABASE_ID)
    const wrapper = await mountAction('slack_write_message', {}, database)
    await flushPromises()

    // Fetched once, for the field's own database, and nothing else.
    expect(testApp.mock.history.get.map((request) => request.url)).toEqual([
      `application/${OWN_DATABASE_ID}/integrations/`,
    ])
    const dropdown = wrapper.findComponent({ name: 'IntegrationDropdown' })
    expect(dropdown.exists()).toBe(true)
    expect(dropdown.props('integrations').map((i) => i.name)).toEqual(['Bot'])
  })

  test('a repopulated application fetches its integrations again', async () => {
    // The applications endpoint carries no integrations, so every refetch
    // empties the list. Remembering the load anywhere but on the application
    // itself leaves the dropdown permanently empty after one.
    await seedApplications()
    testApp.mock
      .onGet(`application/${OWN_DATABASE_ID}/integrations/`)
      .reply(200, [{ id: 7, type: 'slack_bot', name: 'Bot', order: '1' }])

    const database = testApp.store.getters['application/get'](OWN_DATABASE_ID)
    await mountAction('slack_write_message', {}, database)
    await flushPromises()
    expect(testApp.mock.history.get).toHaveLength(1)

    // What `application/fetchAll` does on a workspace switch or a re-login.
    await seedApplications()
    const repopulated =
      testApp.store.getters['application/get'](OWN_DATABASE_ID)
    const wrapper = await mountAction('slack_write_message', {}, repopulated)
    await flushPromises()

    expect(testApp.mock.history.get).toHaveLength(2)
    expect(
      wrapper
        .findComponent({ name: 'IntegrationDropdown' })
        .props('integrations')
    ).toHaveLength(1)
  })

  test('a failed integrations fetch is reported, not left empty', async () => {
    await seedApplications()
    // Mimic a real API error: it carries a `handler` so notifyIf reports it
    // instead of re-throwing.
    const notifyIfHandler = vi.fn()
    const apiError = Object.assign(new Error('boom'), {
      handler: { notifyIf: notifyIfHandler },
    })
    const database = testApp.store.getters['application/get'](OWN_DATABASE_ID)
    const dispatch = vi
      .spyOn(testApp.store, 'dispatch')
      .mockImplementation((action, payload) =>
        action === 'integration/fetch'
          ? Promise.reject(apiError)
          : Promise.resolve()
      )

    await mountAction('slack_write_message', {}, database)
    await flushPromises()

    // Reported to the user rather than left as an unhandled rejection, and
    // not remembered as loaded, so reopening the editor tries again instead
    // of claiming the database has no bot.
    expect(notifyIfHandler).toHaveBeenCalled()
    expect(database._integrationsLoadedOnce).toBeFalsy()

    dispatch.mockRestore()
  })

  test('a row action fetches no integrations', async () => {
    await seedApplications()

    await mountAction('local_baserow_create_row')
    await flushPromises()

    expect(testApp.mock.history.get).toHaveLength(0)
  })

  test('the service form gets the workspace databases', async () => {
    await seedApplications()

    const wrapper = await mountAction('local_baserow_create_row')

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

    const wrapper = await mountAction('local_baserow_create_row')

    // With no integration the table selector was never rendered at all, so
    // the action could not be configured.
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

    // A newly added action has nothing saved and so no schema, which used to
    // make the form claim the table had no writable fields.
    const wrapper = await mountAction('local_baserow_create_row', {
      table_id: 2,
    })
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

    // Update row's form is a thin wrapper that forwards $attrs, so the props
    // have to be decided from the action type, not from the form component.
    const wrapper = await mountAction('local_baserow_update_row', {
      table_id: 2,
    })
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

    const wrapper = await mountAction('local_baserow_create_row', {
      table_id: 2,
    })
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

    const wrapper = await mountAction('local_baserow_create_row', {
      table_id: 1,
    })
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

  test('a table whose fields cannot be fetched is marked unavailable', async () => {
    // Left unregistered, the explorer falls back to the schema of the last
    // save, which describes the table this action pointed at before. Marked
    // rather than registered empty, so it stays apart from a table that really
    // has no fields and cannot overwrite what another action fetched.
    await seedApplications()
    testApp.dontFailOnErrorResponses()
    testApp.mock.onGet('/database/fields/table/1/').reply(200, TABLE_FIELDS)
    testApp.mock.onGet('/database/fields/table/2/').reply(500)
    const registerTableFields = vi.fn()

    const wrapper = await testApp.mount(DatabaseWorkflowActionWithService, {
      props: {
        workflowAction: {
          id: 1,
          type: 'local_baserow_create_row',
          service: {},
        },
        database: { id: OWN_DATABASE_ID, workspace: WORKSPACE },
        defaultValues: { service: { table_id: 1 } },
      },
      global: { provide: { workspace: WORKSPACE, registerTableFields } },
    })
    await flushPromises()

    await wrapper.setProps({ defaultValues: { service: { table_id: 2 } } })
    wrapper.vm.values.service = { table_id: 2 }
    await flushPromises()

    expect(registerTableFields).toHaveBeenCalledWith(1, TABLE_FIELDS)
    expect(registerTableFields).toHaveBeenLastCalledWith(2, FIELDS_UNAVAILABLE)
  })

  test('re-picking the table already selected keeps the mappings visible', async () => {
    await seedApplications()
    testApp.mock.onGet('/database/fields/table/2/').reply(200, TABLE_FIELDS)

    const wrapper = await mountAction('local_baserow_create_row', {
      table_id: 2,
    })
    await flushPromises()

    const serviceForm = wrapper.findComponent({
      name: 'LocalBaserowUpsertRowServiceForm',
    })
    expect(wrapper.findComponent({ name: 'FieldMappingsForm' }).exists()).toBe(
      true
    )

    // The table dropdown is not clearable, so re-picking the selected table
    // re-emits the same id, and nothing should refetch.
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

    const wrapper = await mountAction('local_baserow_create_row', {
      table_id: 1,
    })
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

    const wrapper = await mountAction('local_baserow_create_row', {})

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

    const wrapper = await mountAction('local_baserow_create_row', {})

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

    const wrapper = await mountAction('local_baserow_delete_row', {
      table_id: 2,
    })
    await flushPromises()

    // Delete row has no field mappings, so fetching them would be a wasted
    // request and the props would land as stray attributes on its form.
    expect(testApp.mock.history.get).toHaveLength(0)
    expect(wrapper.vm.supportsFieldMappings).toBe(false)
    expect(wrapper.vm.mappableFields).toBeNull()
  })

  test('the delete row action also gets the databases', async () => {
    await seedApplications()

    const wrapper = await mountAction('local_baserow_delete_row')

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

  describe('what a click remembered', () => {
    test('an HTTP action that nothing has clicked says so', async () => {
      await seedApplications()

      const wrapper = await mountAction('http_request', { url: 'x' })

      // The endpoint has not answered, so there is no payload to show. Saying
      // nothing here is what left the missing body unexplained.
      expect(wrapper.findComponent({ name: 'SampleDataViewer' }).exists()).toBe(
        false
      )
      const alert = wrapper.find('.alert')
      expect(alert.exists()).toBe(true)
      // `$t` returns the key in the test env, so the copy is pinned separately.
      expect(alert.text()).toContain(
        'databaseWorkflowActionWithService.nothingCapturedYet'
      )
      // The click runs the whole button, which is the part a preview elsewhere
      // in Baserow has no reason to warn about.
      expect(en.databaseWorkflowActionWithService.nothingCapturedYet).toContain(
        "button's other actions run as well"
      )
    })

    test('an HTTP action that has answered shows what came back', async () => {
      await seedApplications()

      const wrapper = await mountAction('http_request', {
        url: 'x',
        sample_data: { data: { body: { title: 'Sample' }, status_code: 200 } },
      })

      expect(wrapper.find('.alert').exists()).toBe(false)
      const viewer = wrapper.findComponent({ name: 'SampleDataViewer' })
      expect(viewer.exists()).toBe(true)
      // What is stored is the whole dispatch result. The viewer gets what is
      // inside its `data` wrapper, so the paths it shows are the ones the
      // explorer offers: `body`, `headers`, `raw_body`, `status_code`.
      expect(viewer.props('sampleData')).toEqual({
        body: { title: 'Sample' },
        status_code: 200,
      })
    })

    test('an answer with nothing inside its wrapper counts as nothing', async () => {
      await seedApplications()

      const wrapper = await mountAction('http_request', {
        url: 'x',
        sample_data: { status: 'completed' },
      })

      expect(wrapper.findComponent({ name: 'SampleDataViewer' }).exists()).toBe(
        false
      )
      expect(wrapper.find('.alert').exists()).toBe(true)
    })

    test('a click that captured nothing says why', async () => {
      await seedApplications()

      const wrapper = await mountAction('http_request', {
        url: 'x',
        sample_data: { _error: 'The last click was answered with 404.' },
      })

      // Shown in place of the note asking for a click that has already
      // happened, which would otherwise stay exactly as it was.
      const viewer = wrapper.findComponent({ name: 'SampleDataViewer' })
      expect(viewer.exists()).toBe(true)
      expect(viewer.props('sampleData')).toBe(
        'The last click was answered with 404.'
      )
      expect(viewer.props('isError')).toBe(true)
      expect(wrapper.find('.alert').exists()).toBe(false)
    })

    test('a row action is left alone: its shape comes from the table', async () => {
      await seedApplications()

      const wrapper = await mountAction('local_baserow_create_row')

      expect(wrapper.find('.button-field-action-form__payload').exists()).toBe(
        false
      )
    })
  })
})
