import { vi } from 'vitest'
import { TestApp } from '@baserow/test/helpers/testApp'
import UpdateFieldContext from '@baserow/modules/database/components/field/UpdateFieldContext'
import CreateFieldContext from '@baserow/modules/database/components/field/CreateFieldContext'

/**
 * `has_workflow_actions` is derived server side and returned by the field
 * create/update response, which the store commits verbatim. That response is
 * built before `saveWorkflowActions` runs, so the flag describes the field as
 * it was one request earlier and every cell renders the wrong branch until the
 * page is reloaded. These tests pin that the contexts correct the flag once
 * the actions have been saved, in both directions.
 */
describe('field contexts keep has_workflow_actions in sync', () => {
  let testApp = null
  let client = null
  // What the stubbed field form reports it has server side. `null` stands for
  // a field type that has no notion of workflow actions.
  let reportedWorkflowActions = null

  const table = { id: 1 }
  const view = { id: 1, type: 'grid' }
  const database = { id: 1, workspace: { id: 1 } }
  const allFieldsInTable = [{ id: 1, type: 'text', name: 'Name' }]

  // The action editor itself is exercised by fieldButtonSubForm.spec.js. Only
  // what the context does with the form's answer matters here, and stubbing
  // the form also keeps this test off the sub-form's own request traffic.
  const FieldFormStub = {
    name: 'FieldForm',
    props: [
      'table',
      'view',
      'primary',
      'forcedType',
      'allFieldsInTable',
      'defaultValues',
      'database',
    ],
    methods: {
      async saveWorkflowActions() {},
      hasWorkflowActions() {
        return reportedWorkflowActions
      },
      reset() {},
      handleErrorByForm() {
        return false
      },
      isDescriptionFieldNotEmpty() {
        return false
      },
    },
    template: '<div />',
  }

  const buttonField = (overrides = {}) => ({
    id: 7,
    table_id: 1,
    name: 'Go',
    type: 'button',
    label: 'Go',
    has_workflow_actions: false,
    primary: false,
    read_only: false,
    related_fields: [],
    ...overrides,
  })

  const mountContext = async (component, propsData) => {
    const wrapper = await testApp.mount(component, {
      propsData,
      global: { stubs: { FieldForm: FieldFormStub } },
    })
    wrapper.vm.$refs.context.forceRender()
    await wrapper.vm.$nextTick()
    return wrapper
  }

  beforeEach(async () => {
    testApp = new TestApp()
    reportedWorkflowActions = null
    client = testApp.getApp().$client
    vi.spyOn(client, 'get').mockResolvedValue({ data: [] })
    vi.spyOn(client, 'post').mockResolvedValue({ data: {} })
    vi.spyOn(client, 'patch').mockResolvedValue({ data: {} })
    vi.spyOn(client, 'delete').mockResolvedValue({ data: {} })
  })

  afterEach(async () => {
    await testApp.afterEach()
    vi.restoreAllMocks()
  })

  test('a first action flips the flag the update response left false', async () => {
    const field = buttonField()
    await testApp.store.dispatch('field/forceSetFields', { fields: [field] })

    const wrapper = await mountContext(UpdateFieldContext, {
      table,
      field,
      view,
      allFieldsInTable,
      database,
    })

    // The response was built before the action existed.
    client.patch.mockResolvedValue({
      data: { ...field, has_workflow_actions: false },
    })
    reportedWorkflowActions = true

    await wrapper.vm.submit({ name: 'Go', type: 'button', label: 'Go' })
    await wrapper.emitted('update')[0][0].callback()

    expect(testApp.store.getters['field/get'](7).has_workflow_actions).toBe(
      true
    )
  })

  test('losing the last action clears the flag the update response left true', async () => {
    const field = buttonField({ has_workflow_actions: true })
    await testApp.store.dispatch('field/forceSetFields', { fields: [field] })

    const wrapper = await mountContext(UpdateFieldContext, {
      table,
      field,
      view,
      allFieldsInTable,
      database,
    })

    // The response still describes the action that the save then removed.
    client.patch.mockResolvedValue({
      data: { ...field, has_workflow_actions: true },
    })
    reportedWorkflowActions = false

    await wrapper.vm.submit({ name: 'Go', type: 'button', label: 'Go' })
    await wrapper.emitted('update')[0][0].callback()

    expect(testApp.store.getters['field/get'](7).has_workflow_actions).toBe(
      false
    )
  })

  test('a field type without workflow actions is left alone', async () => {
    const field = {
      id: 8,
      table_id: 1,
      name: 'Name',
      type: 'text',
      primary: false,
      read_only: false,
      related_fields: [],
    }
    await testApp.store.dispatch('field/forceSetFields', { fields: [field] })

    const wrapper = await mountContext(UpdateFieldContext, {
      table,
      field,
      view,
      allFieldsInTable,
      database,
    })

    client.patch.mockResolvedValue({ data: { ...field } })
    reportedWorkflowActions = null

    await wrapper.vm.submit({ name: 'Name', type: 'text' })
    await wrapper.emitted('update')[0][0].callback()

    expect(
      testApp.store.getters['field/get'](8).has_workflow_actions
    ).toBeUndefined()
  })

  test('a created button field is stored with the flag its actions imply', async () => {
    const wrapper = await mountContext(CreateFieldContext, {
      table,
      view,
      allFieldsInTable,
      database,
    })

    client.post.mockResolvedValue({
      data: buttonField({ has_workflow_actions: false }),
    })
    reportedWorkflowActions = true

    await wrapper.vm.submit({ name: 'Go', type: 'button', label: 'Go' })
    await wrapper.emitted('field-created')[0][0].callback()

    expect(testApp.store.getters['field/get'](7).has_workflow_actions).toBe(
      true
    )
  })
})
