import { vi } from 'vitest'
import { TestApp } from '@baserow/test/helpers/testApp'
import FieldButtonSubForm from '@baserow/modules/database/components/field/FieldButtonSubForm'

describe('FieldButtonSubForm', () => {
  let testApp = null

  beforeAll(() => {
    testApp = new TestApp()
  })

  afterEach(() => {
    testApp.afterEach()
  })

  const mountForm = async (defaultValues = {}) =>
    testApp.mount(FieldButtonSubForm, {
      propsData: {
        table: { id: 1 },
        view: null,
        primary: false,
        allFieldsInTable: [{ id: 1, type: 'text', name: 'Name' }],
        name: 'button',
        database: { id: 1, workspace: { id: 1 } },
        defaultValues,
      },
    })

  test('valid stored formula produces a valid form', async () => {
    const wrapper = await mountForm({
      type: 'button',
      label: 'Open',
      url_formula: { formula: "get('fields.field_1')", mode: 'advanced' },
    })
    expect(wrapper.vm.isFormValid()).toBe(true)
    expect(wrapper.vm.getFormValues().url_formula.formula).toBe(
      "get('fields.field_1')"
    )
  })

  test('a missing label blocks submission', async () => {
    const wrapper = await mountForm({
      type: 'button',
      url_formula: { formula: "get('fields.field_1')", mode: 'advanced' },
    })
    wrapper.vm.v$.$touch()
    expect(wrapper.vm.isFormValid()).toBe(false)
  })

  test('empty formula blocks submission', async () => {
    const wrapper = await mountForm({
      type: 'button',
      label: 'Open',
      url_formula: { formula: '', mode: 'simple' },
    })
    wrapper.vm.v$.$touch()
    expect(wrapper.vm.isFormValid()).toBe(false)
  })

  test('an invalid formula blocks submission', async () => {
    const wrapper = await mountForm({
      type: 'button',
      label: 'Open',
      url_formula: { formula: "get('fields.field_1')", mode: 'advanced' },
    })
    expect(wrapper.vm.isFormValid()).toBe(true)
    // The formula input only reports parse errors through update:invalid.
    wrapper.vm.urlInvalid = true
    expect(wrapper.vm.isFormValid()).toBe(false)
  })

  // Nested rather than a sibling describe, because these tests reuse the
  // `testApp`/`mountForm` set up above.
  describe('workflow actions', () => {
    beforeEach(() => {
      // Replace the real client methods with spies so requests never hit
      // the network, and so calls can be asserted on directly.
      const client = testApp.getApp().$client
      vi.spyOn(client, 'get').mockResolvedValue({ data: [] })
      vi.spyOn(client, 'post').mockResolvedValue({ data: {} })
      vi.spyOn(client, 'patch').mockResolvedValue({ data: {} })
      vi.spyOn(client, 'delete').mockResolvedValue({ data: {} })
    })

    afterEach(() => {
      vi.restoreAllMocks()
    })

    test('cancelling after adding an action issues no api calls', async () => {
      const wrapper = await mountForm({ type: 'button', label: 'Go' })

      wrapper.vm.localActions = [{ type: 'create_row', service: {} }]

      // No save call is made. Nothing should have reached the client.
      expect(wrapper.vm.$client.post).not.toHaveBeenCalled()
      expect(wrapper.vm.$client.patch).not.toHaveBeenCalled()
      expect(wrapper.vm.$client.delete).not.toHaveBeenCalled()
    })

    test('saving creates a new action then applies its config', async () => {
      const wrapper = await mountForm({ type: 'button', label: 'Go', id: 7 })
      wrapper.vm.serverActions = []
      wrapper.vm.localActions = [
        { type: 'create_row', service: { table_id: 3 } },
      ]

      const created = { data: { id: 55, type: 'create_row' } }
      wrapper.vm.$client.post.mockResolvedValueOnce(created)

      await wrapper.vm.saveWorkflowActions(7)

      expect(wrapper.vm.$client.post).toHaveBeenCalledWith(
        'database/field/7/workflow_actions/',
        { type: 'create_row' }
      )
      expect(wrapper.vm.$client.patch).toHaveBeenCalledWith(
        'database/workflow_action/55/',
        { service: { table_id: 3 } }
      )
    })

    test('saving deletes a removed action and orders the rest', async () => {
      const wrapper = await mountForm({ type: 'button', label: 'Go', id: 7 })
      wrapper.vm.serverActions = [
        { id: 1, type: 'create_row', service: {} },
        { id: 2, type: 'delete_row', service: {} },
      ]
      wrapper.vm.localActions = [{ id: 2, type: 'delete_row', service: {} }]

      await wrapper.vm.saveWorkflowActions(7)

      expect(wrapper.vm.$client.delete).toHaveBeenCalledWith(
        'database/workflow_action/1/'
      )
      expect(wrapper.vm.$client.post).toHaveBeenCalledWith(
        'database/field/7/workflow_actions/order/',
        { workflow_action_ids: [2] }
      )
    })

    test('editing an already-edited action accumulates both edits', async () => {
      // Pins the defaultValues staleness concern: DatabaseWorkflowActionWithService
      // merges against `defaultValues.service`, so ButtonFieldActionList must
      // keep that prop in sync as localActions changes, or a second edit
      // would merge against the pre-first-edit snapshot and lose it.
      const wrapper = await mountForm({ type: 'button', label: 'Go', id: 7 })
      wrapper.vm.serverActions = [{ id: 1, type: 'create_row', service: {} }]
      wrapper.vm.localActions = [{ id: 1, type: 'create_row', service: {} }]
      await wrapper.vm.$nextTick()

      const list = wrapper.findComponent({ name: 'ButtonFieldActionList' })

      // First edit, as DatabaseWorkflowActionWithService would emit it.
      list.vm.onActionValuesChanged(0, { service: { table_id: 3 } })
      await wrapper.vm.$nextTick()

      expect(wrapper.vm.localActions[0].service).toEqual({ table_id: 3 })
      // The list's own `value` prop must have picked up the update, or the
      // second edit below would merge against the stale first snapshot.
      expect(list.vm.value[0].service).toEqual({ table_id: 3 })

      // Second edit. A real DatabaseWorkflowActionWithService would compute
      // this by merging `defaultValues.service` (now { table_id: 3 } if the
      // prop stayed live) with its own new field.
      list.vm.onActionValuesChanged(0, {
        service: { table_id: 3, row_id: 9 },
      })
      await wrapper.vm.$nextTick()

      expect(wrapper.vm.localActions[0].service).toEqual({
        table_id: 3,
        row_id: 9,
      })
    })
  })
})
