import { vi } from 'vitest'
import { TestApp } from '@baserow/test/helpers/testApp'
import FieldButtonSubForm from '@baserow/modules/database/components/field/FieldButtonSubForm'
import InjectedFormulaInput from '@baserow/modules/core/components/formula/InjectedFormulaInput'

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

    test('cancelling drops the discarded action from the reopened editor', async () => {
      // Regression test: UpdateFieldContext keeps this sub-form mounted per
      // field, so reopening the editor after a cancel shows whatever is still
      // buffered. Cancel goes through FieldForm.reset(), which the form mixin
      // forwards to child forms, so the buffer has to be rebuilt there. If it
      // is not, the discarded action is still listed and a later save creates
      // it for real.
      const wrapper = await mountForm({ type: 'button', label: 'Go', id: 7 })
      wrapper.vm.serverActions = [{ id: 1, type: 'create_row', service: {} }]
      wrapper.vm.localActions = [{ id: 1, type: 'create_row', service: {} }]

      wrapper.vm.localActions = [
        ...wrapper.vm.localActions,
        { type: 'delete_row', service: {} },
      ]

      await wrapper.vm.reset()

      expect(wrapper.vm.localActions).toEqual([
        { id: 1, type: 'create_row', service: {} },
      ])

      // The rebuilt buffer is a copy, so editing it cannot write through to
      // the server list that the next reconciliation diffs against.
      wrapper.vm.localActions[0].service.table_id = 3
      expect(wrapper.vm.serverActions[0].service).toEqual({})

      // Nothing was persisted by the cancel itself.
      expect(wrapper.vm.$client.post).not.toHaveBeenCalled()
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

    test('a created action is configured with the service type the server assigned', async () => {
      // A buffered service carries no `type` until the server has made one,
      // and the API's polymorphic service serializer refuses a payload it
      // cannot type (it 500s). The follow-up update therefore has to take the
      // type from the service the create just returned, or a brand new
      // action's configuration is never persisted.
      const wrapper = await mountForm({ type: 'button', label: 'Go', id: 7 })
      wrapper.vm.serverActions = []
      wrapper.vm.localActions = [
        { type: 'create_row', service: { table_id: 3 } },
      ]

      wrapper.vm.$client.post.mockResolvedValueOnce({
        data: {
          id: 55,
          type: 'create_row',
          service: { id: 9, type: 'local_baserow_upsert_row', table_id: null },
        },
      })

      await wrapper.vm.saveWorkflowActions(7)

      expect(wrapper.vm.$client.patch).toHaveBeenCalledWith(
        'database/workflow_action/55/',
        { service: { type: 'local_baserow_upsert_row', table_id: 3 } }
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
      // merges the nested service form's payload against `defaultValues.service`
      // (see DatabaseWorkflowActionWithService.vue), so ButtonFieldActionList
      // must keep that prop live as localActions changes, or a second, partial
      // edit would merge against the pre-first-edit snapshot and lose it.
      //
      // This drives the real ButtonFieldActionList -> DatabaseWorkflowActionWithService
      // chain, including its merge line. Only the innermost create_row form is
      // stubbed, so each `values-changed` below goes through the actual merge.
      const StubServiceForm = {
        name: 'StubServiceForm',
        props: ['application', 'service', 'serviceType', 'defaultValues'],
        emits: ['values-changed'],
        template: '<div />',
      }
      const serviceType = testApp
        .getRegistry()
        .get('service', 'local_baserow_create_row')
      vi.spyOn(serviceType, 'formComponent', 'get').mockReturnValue(
        StubServiceForm
      )

      const wrapper = await mountForm({ type: 'button', label: 'Go', id: 7 })
      wrapper.vm.serverActions = [{ id: 1, type: 'create_row', service: {} }]
      wrapper.vm.localActions = [{ id: 1, type: 'create_row', service: {} }]
      await wrapper.vm.$nextTick()

      const stubForm = wrapper.findComponent({ name: 'StubServiceForm' })

      // First edit: a genuinely partial payload, as the real form emits.
      stubForm.vm.$emit('values-changed', { table_id: 3 })
      await wrapper.vm.$nextTick()

      expect(wrapper.vm.localActions[0].service).toEqual({ table_id: 3 })

      // Second edit: only the new field, nothing else. This only survives if
      // DatabaseWorkflowActionWithService merged against a live
      // `defaultValues.service`, not the pre-first-edit `{}` snapshot.
      stubForm.vm.$emit('values-changed', { row_id: 9 })
      await wrapper.vm.$nextTick()

      expect(wrapper.vm.localActions[0].service).toEqual({
        table_id: 3,
        row_id: 9,
      })
    })

    test('hasWorkflowActions follows what the save left on the server', async () => {
      // The field create/update response computes `has_workflow_actions`
      // before these calls are made, so the contexts patch the store from
      // this instead. It has to answer for what really persisted, in both
      // directions.
      const wrapper = await mountForm({ type: 'button', label: 'Go', id: 7 })
      expect(wrapper.vm.hasWorkflowActions()).toBe(false)

      wrapper.vm.serverActions = []
      wrapper.vm.localActions = [{ type: 'create_row', service: {} }]
      wrapper.vm.$client.post.mockResolvedValueOnce({
        data: { id: 55, type: 'create_row' },
      })
      wrapper.vm.$client.get.mockResolvedValueOnce({
        data: [{ id: 55, type: 'create_row', service: {} }],
      })

      await wrapper.vm.saveWorkflowActions(7)

      expect(wrapper.vm.hasWorkflowActions()).toBe(true)

      wrapper.vm.localActions = []
      wrapper.vm.$client.get.mockResolvedValueOnce({ data: [] })

      await wrapper.vm.saveWorkflowActions(7)

      expect(wrapper.vm.hasWorkflowActions()).toBe(false)
    })

    test('the action editor stays out of the field payload', async () => {
      // The nested action forms register up the form chain, so without an
      // override the field create/update body would also carry `service` and
      // whatever the service form put in it. DRF ignores unknown keys today,
      // but the field payload must not be coupled to the action editor.
      const wrapper = await mountForm({ type: 'button', label: 'Go', id: 7 })
      wrapper.vm.localActions = [
        { type: 'create_row', service: { table_id: 3 } },
      ]
      await wrapper.vm.$nextTick()

      // The nested form really did register, or this asserts nothing.
      expect(wrapper.vm.registeredChildForms.length).toBeGreaterThan(0)
      expect(Object.keys(wrapper.vm.getFormValues()).sort()).toEqual([
        'label',
        'url_formula',
      ])
    })

    test('mounting on a non-button field does not fetch workflow actions', async () => {
      // FieldForm swaps this sub-form in live as the user browses the type
      // dropdown. `defaultValues` is still the persisted field, which may be
      // of a different type with a real id.
      const wrapper = await mountForm({ type: 'text', label: 'Go', id: 7 })

      expect(wrapper.vm.$client.get).not.toHaveBeenCalled()
    })

    test('a failed fetch on mount degrades to an empty list', async () => {
      const client = testApp.getApp().$client
      client.get.mockRejectedValueOnce(
        Object.assign(new Error('not found'), {
          handler: { notifyIf: () => {} },
        })
      )

      const wrapper = await mountForm({ type: 'button', label: 'Go', id: 7 })

      expect(wrapper.vm.serverActions).toEqual([])
      expect(wrapper.vm.localActions).toEqual([])
    })

    test('a second save does not recreate an action the first save already created', async () => {
      // Regression test: UpdateFieldContext mounts this component once per
      // field and keeps it mounted across open/edit/save cycles (Context.vue
      // uses v-if="openedOnce"), so serverActions/localActions must reflect
      // what really exists server-side after each save, or reconciliation on
      // the next save treats an already-created action as new again.
      const wrapper = await mountForm({ type: 'button', label: 'Go', id: 7 })
      wrapper.vm.serverActions = [{ id: 1, type: 'create_row', service: {} }]
      wrapper.vm.localActions = [
        { id: 1, type: 'create_row', service: {} },
        { type: 'delete_row', service: {} },
      ]

      let nextId = 99
      wrapper.vm.$client.post.mockImplementation((url, body) => {
        if (url === 'database/field/7/workflow_actions/') {
          return Promise.resolve({ data: { id: nextId++, type: body.type } })
        }
        return Promise.resolve({ data: {} })
      })
      wrapper.vm.$client.get.mockResolvedValueOnce({
        data: [
          { id: 1, type: 'create_row', service: {} },
          { id: 99, type: 'delete_row', service: {} },
        ],
      })

      await wrapper.vm.saveWorkflowActions(7)

      // The re-sync picked up the real id: the buffer no longer has an
      // id-less action for the next reconciliation to treat as new.
      expect(wrapper.vm.serverActions.map((a) => a.id)).toEqual([1, 99])
      expect(wrapper.vm.localActions.map((a) => a.id)).toEqual([1, 99])

      wrapper.vm.$client.post.mockClear()
      wrapper.vm.$client.get.mockResolvedValueOnce({
        data: [
          { id: 1, type: 'create_row', service: {} },
          { id: 99, type: 'delete_row', service: {} },
          { id: 100, type: 'create_row', service: {} },
        ],
      })

      // Add a third action and save again on the same mounted instance,
      // without a remount in between.
      wrapper.vm.localActions = [
        ...wrapper.vm.localActions,
        { type: 'create_row', service: {} },
      ]

      await wrapper.vm.saveWorkflowActions(7)

      const createCalls = wrapper.vm.$client.post.mock.calls.filter(
        ([url]) => url === 'database/field/7/workflow_actions/'
      )
      // Only the new (third) action is created. A2 (id 99) must not be
      // recreated.
      expect(createCalls).toHaveLength(1)
      expect(createCalls[0][1]).toEqual({ type: 'create_row' })
    })
  })

  describe('formula injection', () => {
    // A "create a row" action's field mappings render their formula input
    // through the shared `InjectedFormulaInput`, which resolves the component
    // to render from an injected `formulaComponent`. Nothing in the database
    // module provided one, so the injection was undefined and Vue rendered a
    // bare comment node: the mapping showed an empty area instead of an input.
    const mountInjectedInput = async (formWrapper, attrs = {}) =>
      testApp.mount(InjectedFormulaInput, {
        attrs,
        global: { provide: formWrapper.vm.$.provides },
      })

    test('the sub-form provides what InjectedFormulaInput injects', async () => {
      const wrapper = await mountForm({ type: 'button', label: 'Go' })
      const provides = wrapper.vm.$.provides

      expect(provides.formulaComponent).toBeTruthy()
      // Only the clicked row resolves in a button action's arguments.
      expect(provides.dataProvidersAllowed).toEqual(['row'])
    })

    test('InjectedFormulaInput renders a real input under the sub-form', async () => {
      const form = await mountForm({ type: 'button', label: 'Go' })

      const input = await mountInjectedInput(form, {
        modelValue: { formula: "'hi'", mode: 'simple' },
      })

      // The defect: without a provided component this rendered nothing but a
      // comment node, so both of these were false/empty.
      expect(input.findComponent({ name: 'FormulaInputField' }).exists()).toBe(
        true
      )
      expect(input.html()).not.toBe('<!---->')
    })

    test('the injected input offers the clicked row fields', async () => {
      const form = await mountForm({ type: 'button', label: 'Go' })

      const input = await mountInjectedInput(form, {
        modelValue: { formula: "'hi'", mode: 'simple' },
      })

      const formulaInput = input.findComponent({ name: 'DatabaseFormulaInput' })
      const dataGroup = formulaInput.vm.nodesHierarchy.find(
        (group) => group.type === 'data'
      )
      // `allFieldsInTable` above holds a single "Name" field.
      const rowNode = dataGroup.nodes.find((node) => node.identifier === 'row')
      expect(rowNode.nodes.map((node) => node.identifier)).toEqual([
        'id',
        'field_1',
      ])
    })

    test('editing the injected input emits the whole value object', async () => {
      const form = await mountForm({ type: 'button', label: 'Go' })

      const input = await mountInjectedInput(form, {
        modelValue: { formula: "'old'", mode: 'simple' },
      })

      input
        .findComponent({ name: 'DatabaseFormulaInput' })
        .vm.onFormulaChanged("'new'")

      expect(input.emitted('update:modelValue')[0]).toEqual([
        { formula: "'new'", mode: 'simple' },
      ])
    })
  })
})
