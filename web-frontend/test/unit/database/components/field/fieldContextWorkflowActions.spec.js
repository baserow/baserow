import { vi } from 'vitest'
import { TestApp } from '@baserow/test/helpers/testApp'
import UpdateFieldContext from '@baserow/modules/database/components/field/UpdateFieldContext'
import CreateFieldContext from '@baserow/modules/database/components/field/CreateFieldContext'

/**
 * The field create/update response carries a `has_workflow_actions` computed
 * before `afterFieldSaved` runs, and the store commits it verbatim, so
 * every cell renders the wrong branch until a reload. These tests pin that the
 * contexts correct the flag after the actions are saved, in both directions.
 */
describe('field contexts keep has_workflow_actions in sync', () => {
  let testApp = null
  let client = null
  // What the stubbed field form reports the save response got wrong. `null`
  // stands for a field type with nothing to correct.
  let reportedValuesAfterSave = null
  // Set by a test to make the stubbed form's action save fail.
  let actionSaveError = null

  const table = { id: 1 }
  const view = { id: 1, type: 'grid' }
  const database = { id: 1, workspace: { id: 1 } }
  const allFieldsInTable = [{ id: 1, type: 'text', name: 'Name' }]

  // Only what the context does with the form's answer matters here. The
  // editor itself is covered by fieldButtonSubForm.spec.js.
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
      async afterFieldSaved() {
        if (actionSaveError !== null) {
          throw actionSaveError
        }
      },
      fieldValuesAfterSave() {
        return reportedValuesAfterSave
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
    reportedValuesAfterSave = null
    actionSaveError = null
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

  test('a failed action save leaves the editor open on the edits', async () => {
    // Closing would drop whatever did not save, leaving only a toast. The
    // field itself did save, so its callback still has to run.
    const field = buttonField()
    await testApp.store.dispatch('field/forceSetFields', { fields: [field] })

    const wrapper = await mountContext(UpdateFieldContext, {
      table,
      field,
      view,
      allFieldsInTable,
      database,
    })
    client.patch.mockResolvedValue({ data: { ...field } })
    // Shaped like an API error, which is what `notifyIf` turns into a toast
    // rather than re-throwing.
    actionSaveError = { handler: { notifyIf: vi.fn() } }
    const hide = vi.spyOn(wrapper.vm, 'hide')

    await wrapper.vm.submit({ name: 'Go', type: 'button', label: 'Go' })
    await wrapper.emitted('update')[0][0].callback()

    expect(hide).not.toHaveBeenCalled()
    expect(wrapper.emitted('updated')).toBeUndefined()
    expect(wrapper.vm.loading).toBe(false)
  })

  test('a save that works closes the editor', async () => {
    const field = buttonField()
    await testApp.store.dispatch('field/forceSetFields', { fields: [field] })

    const wrapper = await mountContext(UpdateFieldContext, {
      table,
      field,
      view,
      allFieldsInTable,
      database,
    })
    client.patch.mockResolvedValue({ data: { ...field } })
    const hide = vi.spyOn(wrapper.vm, 'hide')

    await wrapper.vm.submit({ name: 'Go', type: 'button', label: 'Go' })
    await wrapper.emitted('update')[0][0].callback()

    expect(hide).toHaveBeenCalled()
    expect(wrapper.emitted('updated')).toHaveLength(1)
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
    reportedValuesAfterSave = { has_workflow_actions: true }

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
    reportedValuesAfterSave = { has_workflow_actions: false }

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
    reportedValuesAfterSave = null

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
    reportedValuesAfterSave = { has_workflow_actions: true }

    await wrapper.vm.submit({ name: 'Go', type: 'button', label: 'Go' })
    await wrapper.emitted('field-created')[0][0].callback()

    expect(testApp.store.getters['field/get'](7).has_workflow_actions).toBe(
      true
    )
  })

  /**
   * Creating the field and saving its actions are two calls, so the second can
   * fail on a field that exists. Closing on that would discard the whole
   * configuration the user just typed.
   */
  describe('a creation whose actions fail', () => {
    const createWithFailingActions = async () => {
      const wrapper = await mountContext(CreateFieldContext, {
        table,
        view,
        allFieldsInTable,
        database,
      })
      client.post.mockResolvedValue({ data: buttonField() })
      client.patch.mockResolvedValue({ data: buttonField() })
      // Shaped like an API error, which `notifyIf` turns into a toast rather
      // than re-throwing.
      actionSaveError = { handler: { notifyIf: vi.fn() } }

      await wrapper.vm.submit({ name: 'Go', type: 'button', label: 'Go' })
      await wrapper.emitted('field-created')[0][0].callback()
      return wrapper
    }

    test('keeps the editor open on the edits', async () => {
      const wrapper = await createWithFailingActions()

      expect(wrapper.vm.createdField.id).toBe(7)
      expect(wrapper.vm.loading).toBe(false)
      // Without this the form checks its name against the field it just made.
      expect(wrapper.vm.defaultValues.id).toBe(7)
      expect(wrapper.emitted('field-created-callback-done')).toBeUndefined()
      // The field itself did save, so the view still has to hear about it.
      expect(testApp.store.getters['field/get'](7)).toBeTruthy()
    })

    test('saves a retry against that field rather than a second one', async () => {
      const wrapper = await createWithFailingActions()
      const hide = vi.spyOn(wrapper.vm, 'hide')
      actionSaveError = null

      await wrapper.vm.submit({ name: 'Go', type: 'button', label: 'Go' })

      expect(client.post).toHaveBeenCalledTimes(1)
      expect(client.patch).toHaveBeenCalledWith(
        '/database/fields/7/',
        expect.objectContaining({ name: 'Go', type: 'button' })
      )
      expect(hide).toHaveBeenCalled()
      expect(wrapper.vm.createdField).toBe(null)
      expect(wrapper.emitted('field-created-callback-done')).toHaveLength(1)
    })

    test('reports the field once the retry is abandoned', async () => {
      const wrapper = await createWithFailingActions()

      wrapper.vm.hide()

      const done = wrapper.emitted('field-created-callback-done')
      expect(done).toHaveLength(1)
      expect(done[0][0].newField.id).toBe(7)
      expect(wrapper.vm.createdField).toBe(null)
      expect(wrapper.vm.defaultValues.id).toBeUndefined()
    })
  })
})
