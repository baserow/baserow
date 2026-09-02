import { vi } from 'vitest'
import flushPromises from 'flush-promises'
import { TestApp } from '@baserow/test/helpers/testApp'
import FieldButtonSubForm from '@baserow/modules/database/components/field/FieldButtonSubForm'
import { CLIENT_ID_KEY } from '@baserow/modules/database/utils/workflowActionReconciliation'
import ButtonFieldActionList from '@baserow/modules/database/components/field/ButtonFieldActionList'
import ButtonFieldActionForm from '@baserow/modules/database/components/field/ButtonFieldActionForm'
import InjectedFormulaInput from '@baserow/modules/core/components/formula/InjectedFormulaInput'
import { FIELDS_UNAVAILABLE } from '@baserow/modules/database/utils/buttonField'

describe('FieldButtonSubForm', () => {
  let testApp = null

  beforeAll(() => {
    testApp = new TestApp()
  })

  afterEach(() => {
    testApp.afterEach()
  })

  const mountForm = async (
    defaultValues = {},
    allFieldsInTable = [{ id: 1, type: 'text', name: 'Name' }]
  ) =>
    testApp.mount(FieldButtonSubForm, {
      propsData: {
        table: { id: 1 },
        view: null,
        primary: false,
        allFieldsInTable,
        name: 'button',
        database: { id: 1, workspace: { id: 1 } },
        defaultValues,
      },
    })

  test('a stored label produces a valid form', async () => {
    const wrapper = await mountForm({ type: 'button', label: 'Open' })
    expect(wrapper.vm.isFormValid()).toBe(true)
    expect(wrapper.vm.getFormValues().label).toBe('Open')
  })

  test('a missing label blocks submission', async () => {
    const wrapper = await mountForm({ type: 'button' })
    wrapper.vm.v$.$touch()
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

    test('opening the field again re-reads what a click remembered', async () => {
      // A click makes an external action remember the answer it got, so the
      // editor can describe it to the actions after it. This sub-form is not
      // remounted when the field is opened again, so without a re-read the
      // captured body stays missing until the page is reloaded.
      const client = testApp.getApp().$client
      client.get.mockResolvedValueOnce({
        data: [{ id: 7, type: 'http_request', service: { id: 3, url: 'x' } }],
      })
      const wrapper = await mountForm({ type: 'button', id: 5, label: 'Go' })
      await wrapper.vm.$nextTick()
      expect(wrapper.vm.localActions[0].service.sample_data).toBeUndefined()

      client.get.mockResolvedValueOnce({
        data: [
          {
            id: 7,
            type: 'http_request',
            service: { id: 3, url: 'x', sample_data: { data: { body: {} } } },
          },
        ],
      })
      await wrapper.vm.onShow()

      expect(wrapper.vm.localActions[0].service.sample_data).toEqual({
        data: { body: {} },
      })
    })

    test('a field that was never saved has nothing to re-read', async () => {
      const wrapper = await mountForm({ type: 'button', label: 'Go' })
      const client = testApp.getApp().$client
      client.get.mockClear()

      await wrapper.vm.onShow()

      expect(client.get).not.toHaveBeenCalled()
    })

    test('adding an action buffers it without calling the api', async () => {
      // Nothing is persisted until the field form is submitted, which is what
      // makes "add an action, press Cancel" discard it. Driven through the
      // list editor, or the test would pass even if `addAction` hit the API.
      const wrapper = await mountForm({ type: 'button', label: 'Go' })

      wrapper
        .findComponent(ButtonFieldActionList)
        .vm.addAction('local_baserow_create_row')
      await wrapper.vm.$nextTick()

      expect(wrapper.vm.localActions).toEqual([
        {
          [CLIENT_ID_KEY]: expect.any(String),
          type: 'local_baserow_create_row',
          service: {},
        },
      ])
      expect(wrapper.vm.$client.post).not.toHaveBeenCalled()
      expect(wrapper.vm.$client.patch).not.toHaveBeenCalled()
      expect(wrapper.vm.$client.delete).not.toHaveBeenCalled()
    })

    test('the list is not editable until the saved actions have arrived', async () => {
      // Editing before they land either loses the edit to the response, or
      // saves a list missing actions the user never saw, deleting them.
      const client = testApp.getApp().$client
      let resolveGet
      client.get.mockReturnValueOnce(
        new Promise((resolve) => {
          resolveGet = resolve
        })
      )

      const wrapper = await mountForm({ type: 'button', label: 'Go', id: 7 })

      expect(wrapper.findComponent(ButtonFieldActionList).exists()).toBe(false)
      expect(wrapper.find('.loading-spinner').exists()).toBe(true)

      resolveGet({ data: [{ id: 1, type: 'open_url' }] })
      await flushPromises()

      expect(wrapper.findComponent(ButtonFieldActionList).exists()).toBe(true)
      expect(wrapper.vm.localActions).toEqual([{ id: 1, type: 'open_url' }])
    })

    test('cancelling drops the discarded action from the reopened editor', async () => {
      // UpdateFieldContext keeps this sub-form mounted per field, so a cancel
      // has to rebuild the buffer through FieldForm.reset(). Otherwise the
      // discarded action is still listed and a later save creates it for real.
      const wrapper = await mountForm({ type: 'button', label: 'Go', id: 7 })
      wrapper.vm.serverActions = [
        { id: 1, type: 'local_baserow_create_row', service: {} },
      ]
      wrapper.vm.localActions = [
        { id: 1, type: 'local_baserow_create_row', service: {} },
      ]

      wrapper.vm.localActions = [
        ...wrapper.vm.localActions,
        { type: 'local_baserow_delete_row', service: {} },
      ]

      await wrapper.vm.reset()

      expect(wrapper.vm.localActions).toEqual([
        { id: 1, type: 'local_baserow_create_row', service: {} },
      ])

      // The rebuilt buffer is a copy, so editing it cannot write through to
      // the server list that the next reconciliation diffs against.
      wrapper.vm.localActions[0].service.table_id = 3
      expect(wrapper.vm.serverActions[0].service).toEqual({})

      // Nothing was persisted by the cancel itself.
      expect(wrapper.vm.$client.post).not.toHaveBeenCalled()
      expect(wrapper.vm.$client.delete).not.toHaveBeenCalled()
    })

    test('cancelling stops hiding a saved action own error', async () => {
      // The list is kept mounted between opens and its pristine flag is keyed
      // by the saved action's id, so without clearing it the action comes back
      // as it was stored with its error still suppressed.
      const saved = { id: 1, type: 'open_url', url: null, target: 'self' }
      const wrapper = await mountForm({ type: 'button', label: 'Go', id: 7 })
      wrapper.vm.serverActions = [saved]
      wrapper.vm.localActions = [{ ...saved }]
      await wrapper.vm.$nextTick()

      const list = wrapper.vm.$refs.actionList
      expect(
        wrapper.findAll('[data-action-error]').map((node) => node.text())
      ).toEqual(['databaseWorkflowActionType.noUrl'])

      // Retyping it hides the error, which is right while it is being
      // configured.
      list.onActionTypeChanged(0, 'local_baserow_create_row')
      wrapper.vm.localActions = list.value.map((action, index) =>
        index === 0
          ? { ...saved, type: 'local_baserow_create_row', service: {} }
          : action
      )
      await wrapper.vm.$nextTick()
      expect(list.pristineActions).not.toEqual({})

      await wrapper.vm.reset()
      await wrapper.vm.$nextTick()

      expect(list.pristineActions).toEqual({})
      expect(
        wrapper.findAll('[data-action-error]').map((node) => node.text())
      ).toEqual(['databaseWorkflowActionType.noUrl'])
    })

    test('a failed fetch does not drop fields another action fetched', async () => {
      // The map is keyed by table only, so two actions can point at the same
      // one. A fetch that failed for one of them says nothing about the fields
      // the other already has.
      const fields = [{ id: 3, name: 'Name', type: 'text', read_only: false }]
      const wrapper = await mountForm({ type: 'button', label: 'Go', id: 7 })

      wrapper.vm.registerTableFields(2, fields)
      wrapper.vm.registerTableFields(2, FIELDS_UNAVAILABLE)

      expect(wrapper.vm.tableFields[2]).toEqual(fields)

      // A table with nothing fetched still records that the fetch failed.
      wrapper.vm.registerTableFields(3, FIELDS_UNAVAILABLE)
      expect(wrapper.vm.tableFields[3]).toBe(FIELDS_UNAVAILABLE)
    })

    test('an unresolved reference is presentable, so the edits survive', async () => {
      // `notifyIf` rethrows an error with no handler, which would skip the flag
      // that keeps the editor open, and the buffered edits would be discarded
      // with nothing on screen to say why.
      const wrapper = await mountForm({ type: 'button', label: 'Go', id: 7 })
      wrapper.vm.serverActions = []
      wrapper.vm.localActions = [
        {
          _clientId: 'later',
          type: 'open_url',
          url: { formula: "get('previous_action.earlier.id')", mode: 'simple' },
        },
      ]

      await expect(wrapper.vm.afterFieldSaved(7)).rejects.toMatchObject({
        handler: expect.any(Object),
      })
      expect(wrapper.vm.$client.post).not.toHaveBeenCalled()

      // The buffered action is still there to be fixed.
      expect(wrapper.vm.localActions).toHaveLength(1)
    })

    test('a reference between two new actions is rewritten as they are created', async () => {
      // Neither action exists yet, so the second names the first by its client
      // id. Creating in list order means the server id is known by the time the
      // second is sent, and no client id may reach the API.
      const wrapper = await mountForm({ type: 'button', label: 'Go', id: 7 })
      wrapper.vm.serverActions = []
      wrapper.vm.localActions = [
        {
          [CLIENT_ID_KEY]: 'first',
          type: 'local_baserow_create_row',
          service: { table_id: 3 },
        },
        {
          [CLIENT_ID_KEY]: 'second',
          type: 'open_url',
          url: { formula: "get('previous_action.first.id')", mode: 'simple' },
          target: 'self',
        },
      ]
      wrapper.vm.$client.post
        .mockResolvedValueOnce({
          data: { id: 91, type: 'local_baserow_create_row' },
        })
        .mockResolvedValueOnce({ data: { id: 92, type: 'open_url' } })

      await wrapper.vm.afterFieldSaved(7)

      const [firstCall, secondCall] = wrapper.vm.$client.post.mock.calls
      expect(firstCall[1].type).toBe('local_baserow_create_row')
      expect(secondCall[1].url.formula).toBe("get('previous_action.91.id')")
      expect(JSON.stringify(wrapper.vm.$client.post.mock.calls)).not.toContain(
        CLIENT_ID_KEY
      )
    })

    test('ids handed out before a failure are adopted by the references too', async () => {
      // A save that stops part way leaves the created actions carrying real
      // ids. Anything pointing at them has to follow, or the retry finds a
      // client id that nothing maps and can never succeed.
      const wrapper = await mountForm({ type: 'button', label: 'Go', id: 7 })
      wrapper.vm.localActions = [
        { _clientId: 'first', type: 'local_baserow_create_row', service: {} },
        {
          _clientId: 'second',
          type: 'open_url',
          url: { formula: "get('previous_action.first.id')", mode: 'simple' },
        },
      ]

      wrapper.vm.adoptAssignedIds(new Map([['first', 91]]))

      expect(wrapper.vm.localActions[0].id).toBe(91)
      expect(wrapper.vm.localActions[1].url.formula).toBe(
        "get('previous_action.91.id')"
      )
    })

    test('two actions the server forgot do not end up sharing one id', async () => {
      // Deleted by a collaborator, so both are created again, and both came
      // from the server with no client id. Keying them by that would hand one
      // id to the pair, and the next save would lose one of them.
      const wrapper = await mountForm({ type: 'button', label: 'Go', id: 7 })
      wrapper.vm.serverActions = []
      wrapper.vm.localActions = [
        { id: 41, type: 'open_url', url: { formula: "'a'", mode: 'simple' } },
        { id: 42, type: 'open_url', url: { formula: "'b'", mode: 'simple' } },
      ]

      wrapper.vm.$client.post.mockResolvedValueOnce({
        data: { id: 91, type: 'open_url' },
      })
      wrapper.vm.$client.post.mockRejectedValueOnce(new Error('nope'))

      await expect(wrapper.vm.afterFieldSaved(7)).rejects.toThrow()

      const ids = wrapper.vm.localActions.map((action) => action.id)
      expect(new Set(ids).size).toBe(ids.length)
    })

    test('a reference to an action the server forgot follows it', async () => {
      // The first action was deleted by a collaborator while this editor was
      // open, so it is created again under a new id. The second names it by
      // the id it used to have, which now belongs to nothing: left alone, the
      // save succeeds and every click after it fails.
      const wrapper = await mountForm({ type: 'button', label: 'Go', id: 7 })
      wrapper.vm.serverActions = []
      wrapper.vm.localActions = [
        {
          id: 41,
          type: 'local_baserow_create_row',
          service: { table_id: 3 },
        },
        {
          id: 42,
          type: 'open_url',
          url: { formula: "get('previous_action.41.id')", mode: 'simple' },
          target: 'self',
        },
      ]

      wrapper.vm.$client.post
        .mockResolvedValueOnce({
          data: { id: 91, type: 'local_baserow_create_row' },
        })
        .mockResolvedValueOnce({ data: { id: 92, type: 'open_url' } })

      await wrapper.vm.afterFieldSaved(7)

      const [, secondCall] = wrapper.vm.$client.post.mock.calls
      expect(secondCall[1].url.formula).toBe("get('previous_action.91.id')")
    })

    test('the open card follows an action that is given its id', async () => {
      // The card is keyed by what identifies the action, so a save that stops
      // part way would otherwise close the one the user is fixing and drop the
      // flag holding its error back.
      const wrapper = await mountForm({ type: 'button', label: 'Go', id: 7 })
      wrapper.vm.localActions = [
        { [CLIENT_ID_KEY]: 'first', type: 'open_url', url: { formula: "'a'" } },
      ]
      const list = wrapper.findComponent(ButtonFieldActionList)
      list.vm.expandedActions = { first: true }
      list.vm.pristineActions = { first: true }

      wrapper.vm.adoptAssignedIds(new Map([['first', 91]]))
      await wrapper.vm.$nextTick()

      expect(list.vm.expandedActions).toEqual({ 91: true })
      expect(list.vm.pristineActions).toEqual({ 91: true })
    })

    test('saving creates a new action with its config in one call', async () => {
      // One call, so a failure cannot leave an action behind with none of the
      // config the user filled in.
      const wrapper = await mountForm({ type: 'button', label: 'Go', id: 7 })
      wrapper.vm.serverActions = []
      wrapper.vm.localActions = [
        { type: 'local_baserow_create_row', service: { table_id: 3 } },
      ]

      const created = { data: { id: 55, type: 'local_baserow_create_row' } }
      wrapper.vm.$client.post.mockResolvedValueOnce(created)

      await wrapper.vm.afterFieldSaved(7)

      expect(wrapper.vm.$client.post).toHaveBeenCalledWith(
        'database/field/7/workflow_actions/',
        { type: 'local_baserow_create_row', service: { table_id: 3 } }
      )
      expect(wrapper.vm.$client.patch).not.toHaveBeenCalled()
    })

    test('a created service is sent untyped, for the server to name', async () => {
      // The editor calls this service type `local_baserow_create_row` while the
      // API calls it `local_baserow_upsert_row`, so the editor cannot name it.
      // The action type settles which service backs it, so the server does.
      const wrapper = await mountForm({ type: 'button', label: 'Go', id: 7 })
      wrapper.vm.serverActions = []
      wrapper.vm.localActions = [
        { type: 'local_baserow_create_row', service: { table_id: 3 } },
      ]

      wrapper.vm.$client.post.mockResolvedValueOnce({
        data: {
          id: 55,
          type: 'local_baserow_create_row',
          service: { id: 9, type: 'local_baserow_upsert_row', table_id: 3 },
        },
      })

      await wrapper.vm.afterFieldSaved(7)

      const [, payload] = wrapper.vm.$client.post.mock.calls[0]
      expect(payload.service).toEqual({ table_id: 3 })
      expect(payload.service.type).toBeUndefined()
    })

    test('saving a new open url action persists its own config', async () => {
      // `open_url` is backed by no service, so its config is `url`/`target` on
      // the action itself, and it goes out with the create like any other.
      const wrapper = await mountForm({ type: 'button', label: 'Go', id: 7 })
      wrapper.vm.serverActions = []
      wrapper.vm.localActions = [
        {
          type: 'open_url',
          url: { formula: "'x'", mode: 'simple' },
          target: 'blank',
        },
      ]

      wrapper.vm.$client.post.mockResolvedValueOnce({
        data: { id: 55, type: 'open_url' },
      })

      await wrapper.vm.afterFieldSaved(7)

      expect(wrapper.vm.$client.post).toHaveBeenCalledWith(
        'database/field/7/workflow_actions/',
        {
          type: 'open_url',
          url: { formula: "'x'", mode: 'simple' },
          target: 'blank',
        }
      )
    })

    test('a type change keeps the id the editor already holds', async () => {
      // The server swaps the action's type in place, so the PATCH answers with
      // the same action and the order call uses the id the editor holds.
      const wrapper = await mountForm({ type: 'button', label: 'Go', id: 7 })
      wrapper.vm.serverActions = [
        { id: 1, type: 'local_baserow_create_row', service: { table_id: 3 } },
        { id: 2, type: 'local_baserow_delete_row', service: {} },
      ]
      wrapper.vm.localActions = [
        { id: 1, type: 'open_url', url: { formula: "'x'", mode: 'simple' } },
        { id: 2, type: 'local_baserow_delete_row', service: {} },
      ]

      wrapper.vm.$client.patch.mockResolvedValueOnce({
        data: { id: 1, type: 'open_url' },
      })

      await wrapper.vm.afterFieldSaved(7)

      expect(wrapper.vm.$client.patch).toHaveBeenCalledWith(
        'database/workflow_action/1/',
        { type: 'open_url', url: { formula: "'x'", mode: 'simple' } }
      )
      expect(wrapper.vm.$client.post).toHaveBeenCalledWith(
        'database/field/7/workflow_actions/order/',
        { workflow_action_ids: [1, 2] }
      )
    })

    test('a type change into a service type sends no untyped service', async () => {
      // Changing the type resets the config, so the buffered service is `{}`
      // and, never having been round-tripped, carries no nested `type`. The
      // polymorphic serializer answers an untyped payload with a 500, so
      // nothing untyped may reach the wire.
      const wrapper = await mountForm({ type: 'button', label: 'Go', id: 7 })
      wrapper.vm.serverActions = [
        { id: 1, type: 'open_url', url: { formula: "'x'", mode: 'simple' } },
      ]
      wrapper.vm.localActions = [
        { id: 1, type: 'local_baserow_delete_row', service: {} },
      ]

      wrapper.vm.$client.patch.mockResolvedValueOnce({
        data: {
          id: 1,
          type: 'local_baserow_delete_row',
          service: { id: 9, type: 'local_baserow_delete_row' },
        },
      })

      await wrapper.vm.afterFieldSaved(7)

      expect(wrapper.vm.$client.patch).toHaveBeenCalledTimes(1)
      expect(wrapper.vm.$client.patch).toHaveBeenCalledWith(
        'database/workflow_action/1/',
        { type: 'local_baserow_delete_row' }
      )
    })

    test('a type change into a service type types the service it then sends', async () => {
      // The user can change the type and configure the new form before saving.
      // The type change goes on its own, then the config follows once the
      // action is of the new type, typed from what it answered.
      const wrapper = await mountForm({ type: 'button', label: 'Go', id: 7 })
      wrapper.vm.serverActions = [
        { id: 1, type: 'open_url', url: { formula: "'x'", mode: 'simple' } },
      ]
      wrapper.vm.localActions = [
        { id: 1, type: 'local_baserow_create_row', service: { table_id: 3 } },
      ]

      wrapper.vm.$client.patch.mockResolvedValueOnce({
        data: {
          id: 1,
          type: 'local_baserow_create_row',
          service: { id: 9, type: 'local_baserow_upsert_row', table_id: null },
        },
      })

      await wrapper.vm.afterFieldSaved(7)

      expect(wrapper.vm.$client.patch.mock.calls).toEqual([
        ['database/workflow_action/1/', { type: 'local_baserow_create_row' }],
        [
          'database/workflow_action/1/',
          { service: { type: 'local_baserow_upsert_row', table_id: 3 } },
        ],
      ])
      expect(wrapper.vm.$client.post).toHaveBeenCalledWith(
        'database/field/7/workflow_actions/order/',
        { workflow_action_ids: [1] }
      )
    })

    test('a type round trip sends no untyped service back', async () => {
      // Swapping a row's type and back leaves the type matching the server's,
      // so nothing is a type change. The service is still brand new though:
      // the config was reset and re-seeded, so it is untyped, which is what
      // the serializer answers with a 500. Driven through the list editor, so
      // the buffer really does end up that way.
      const wrapper = await mountForm({ type: 'button', label: 'Go', id: 7 })
      const saved = {
        id: 1,
        type: 'local_baserow_create_row',
        service: { id: 9, type: 'local_baserow_upsert_row', table_id: 3 },
      }
      wrapper.vm.serverActions = [saved]
      wrapper.vm.localActions = [{ ...saved, service: { ...saved.service } }]
      await wrapper.vm.$nextTick()

      const list = wrapper.findComponent(ButtonFieldActionList).vm
      list.onActionTypeChanged(0, 'local_baserow_update_row')
      await wrapper.vm.$nextTick()
      list.onActionTypeChanged(0, 'local_baserow_create_row')
      await wrapper.vm.$nextTick()

      // Back on the server's type, but with the config reset: an untyped
      // service where the server has a typed, configured one.
      expect(wrapper.vm.localActions).toEqual([
        {
          id: 1,
          [CLIENT_ID_KEY]: expect.any(String),
          type: 'local_baserow_create_row',
          service: {},
        },
      ])

      await wrapper.vm.afterFieldSaved(7)

      // An empty service says nothing, so it is dropped and the update has
      // nothing left to send. The server keeps its config and the re-fetch
      // puts it back in the buffer, which beats a 500.
      expect(wrapper.vm.$client.patch.mock.calls).toEqual([])
    })

    test('a config edit after a type round trip types its service', async () => {
      // The same round trip, but the user configures the re-seeded form before
      // saving, so the service is untyped and non-empty. It has to reach the
      // wire typed from the action the server already has.
      const wrapper = await mountForm({ type: 'button', label: 'Go', id: 7 })
      wrapper.vm.serverActions = [
        {
          id: 1,
          type: 'local_baserow_create_row',
          service: { id: 9, type: 'local_baserow_upsert_row', table_id: 3 },
        },
      ]
      wrapper.vm.localActions = [
        { id: 1, type: 'local_baserow_create_row', service: { table_id: 5 } },
      ]

      await wrapper.vm.afterFieldSaved(7)

      expect(wrapper.vm.$client.patch).toHaveBeenCalledWith(
        'database/workflow_action/1/',
        { service: { type: 'local_baserow_upsert_row', table_id: 5 } }
      )
    })

    test('a row with no type chosen makes no api calls at all', async () => {
      const wrapper = await mountForm({ type: 'button', label: 'Go', id: 7 })

      wrapper.findComponent(ButtonFieldActionList).vm.addAction()
      await wrapper.vm.$nextTick()

      expect(wrapper.vm.localActions).toEqual([
        { [CLIENT_ID_KEY]: expect.any(String), type: null },
      ])

      wrapper.vm.$client.post.mockClear()

      await wrapper.vm.afterFieldSaved(7)

      expect(wrapper.vm.$client.post).not.toHaveBeenCalled()
      expect(wrapper.vm.$client.patch).not.toHaveBeenCalled()
      expect(wrapper.vm.$client.delete).not.toHaveBeenCalled()
    })

    test('saving deletes a removed action and orders the rest', async () => {
      const wrapper = await mountForm({ type: 'button', label: 'Go', id: 7 })
      wrapper.vm.serverActions = [
        { id: 1, type: 'local_baserow_create_row', service: {} },
        { id: 2, type: 'local_baserow_delete_row', service: {} },
      ]
      wrapper.vm.localActions = [
        { id: 2, type: 'local_baserow_delete_row', service: {} },
      ]

      await wrapper.vm.afterFieldSaved(7)

      expect(wrapper.vm.$client.delete).toHaveBeenCalledWith(
        'database/workflow_action/1/'
      )
      expect(wrapper.vm.$client.post).toHaveBeenCalledWith(
        'database/field/7/workflow_actions/order/',
        { workflow_action_ids: [2] }
      )
    })

    test('editing an already-edited action accumulates both edits', async () => {
      // DatabaseWorkflowActionWithService merges the nested form's payload
      // against `defaultValues.service`, so ButtonFieldActionList has to keep
      // that prop live as localActions changes, or a second partial edit
      // merges against a stale snapshot and loses the first.
      //
      // Only the innermost form is stubbed, so each `values-changed` below
      // goes through the real merge.
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
      wrapper.vm.serverActions = [
        { id: 1, type: 'local_baserow_create_row', service: {} },
      ]
      wrapper.vm.localActions = [
        { id: 1, type: 'local_baserow_create_row', service: {} },
      ]
      await wrapper.vm.$nextTick()

      const stubForm = wrapper.findComponent({ name: 'StubServiceForm' })

      // First edit: a genuinely partial payload, as the real form emits.
      stubForm.vm.$emit('values-changed', { table_id: 3 })
      await wrapper.vm.$nextTick()

      expect(wrapper.vm.localActions[0].service).toEqual({ table_id: 3 })

      // Second edit sends only the new field. It survives only if the merge
      // ran against a live `defaultValues.service`, not the `{}` snapshot.
      stubForm.vm.$emit('values-changed', { row_id: 9 })
      await wrapper.vm.$nextTick()

      expect(wrapper.vm.localActions[0].service).toEqual({
        table_id: 3,
        row_id: 9,
      })
    })

    test('fieldValuesAfterSave follows what the save left on the server', async () => {
      // The field create/update response computes `has_workflow_actions`
      // before these calls, so the contexts patch the store from this instead.
      // It has to answer for what really persisted, in both directions.
      const wrapper = await mountForm({ type: 'button', label: 'Go', id: 7 })
      expect(wrapper.vm.fieldValuesAfterSave()).toEqual({
        has_workflow_actions: false,
      })

      wrapper.vm.serverActions = []
      wrapper.vm.localActions = [
        { type: 'local_baserow_create_row', service: {} },
      ]
      wrapper.vm.$client.post.mockResolvedValueOnce({
        data: { id: 55, type: 'local_baserow_create_row' },
      })
      wrapper.vm.$client.get.mockResolvedValueOnce({
        data: [{ id: 55, type: 'local_baserow_create_row', service: {} }],
      })

      await wrapper.vm.afterFieldSaved(7)

      expect(wrapper.vm.fieldValuesAfterSave()).toEqual({
        has_workflow_actions: true,
      })

      wrapper.vm.localActions = []
      wrapper.vm.$client.get.mockResolvedValueOnce({ data: [] })

      await wrapper.vm.afterFieldSaved(7)

      expect(wrapper.vm.fieldValuesAfterSave()).toEqual({
        has_workflow_actions: false,
      })
    })

    test('the action editor stays out of the field payload', async () => {
      // The nested action forms register up the form chain, so without an
      // override the field payload would also carry `service` and whatever the
      // service form put in it.
      const wrapper = await mountForm({ type: 'button', label: 'Go', id: 7 })
      wrapper.vm.localActions = [
        { type: 'local_baserow_create_row', service: { table_id: 3 } },
      ]
      await wrapper.vm.$nextTick()

      // The nested form really did register, or this asserts nothing.
      expect(wrapper.vm.registeredChildForms.length).toBeGreaterThan(0)
      expect(Object.keys(wrapper.vm.getFormValues()).sort()).toEqual(['label'])
    })

    test('mounting on a non-button field does not fetch workflow actions', async () => {
      // FieldForm swaps this sub-form in live as the user browses the type
      // dropdown. `defaultValues` is still the persisted field, which may be
      // of a different type with a real id.
      const wrapper = await mountForm({ type: 'text', label: 'Go', id: 7 })

      expect(wrapper.vm.$client.get).not.toHaveBeenCalled()
    })

    test('a half saved list keeps the edits, carrying the ids it did get', async () => {
      // Replacing the buffer with the server's list would drop whatever did
      // not save, and keeping it raw would create the saved ones a second
      // time on the retry.
      const wrapper = await mountForm({ type: 'button', label: 'Go', id: 7 })
      wrapper.vm.serverActions = []
      wrapper.vm.localActions = [
        { [CLIENT_ID_KEY]: 'a', type: 'open_url', url: { formula: "'one'" } },
        { [CLIENT_ID_KEY]: 'b', type: 'open_url', url: { formula: "'two'" } },
      ]

      // The first action is created, its config sticks, the second create fails.
      wrapper.vm.$client.post
        .mockResolvedValueOnce({ data: { id: 55, type: 'open_url' } })
        .mockRejectedValueOnce(new Error('boom'))
      wrapper.vm.$client.get.mockResolvedValue({
        data: [{ id: 55, type: 'open_url', url: { formula: "'one'" } }],
      })

      await expect(wrapper.vm.afterFieldSaved(7)).rejects.toThrow('boom')

      // The edits are still there, and the one that saved now knows its id, so
      // a retry updates it rather than creating it again.
      // `target` is the mounted open url form emitting its own default.
      expect(wrapper.vm.localActions).toEqual([
        {
          [CLIENT_ID_KEY]: 'a',
          id: 55,
          type: 'open_url',
          url: { formula: "'one'" },
          target: 'self',
        },
        {
          [CLIENT_ID_KEY]: 'b',
          type: 'open_url',
          url: { formula: "'two'" },
          target: 'self',
        },
      ])
      // The server list is refreshed all the same, so the retry diffs right.
      expect(wrapper.vm.serverActions).toEqual([
        { id: 55, type: 'open_url', url: { formula: "'one'" } },
      ])
    })

    test('a save that works still replaces the buffer with the server list', async () => {
      const wrapper = await mountForm({ type: 'button', label: 'Go', id: 7 })
      wrapper.vm.serverActions = []
      wrapper.vm.localActions = [
        { [CLIENT_ID_KEY]: 'a', type: 'open_url', url: { formula: "'one'" } },
      ]
      wrapper.vm.$client.post.mockResolvedValueOnce({
        data: { id: 55, type: 'open_url' },
      })
      wrapper.vm.$client.get.mockResolvedValue({
        data: [{ id: 55, type: 'open_url', url: { formula: "'one'" } }],
      })

      await wrapper.vm.afterFieldSaved(7)

      expect(wrapper.vm.localActions).toEqual([
        {
          id: 55,
          type: 'open_url',
          url: { formula: "'one'" },
          target: 'self',
        },
      ])
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
      // UpdateFieldContext mounts this component once per field and keeps it
      // mounted across save cycles, so the buffers have to reflect what exists
      // server side after each save, or the next one re-creates it.
      const wrapper = await mountForm({ type: 'button', label: 'Go', id: 7 })
      wrapper.vm.serverActions = [
        { id: 1, type: 'local_baserow_create_row', service: {} },
      ]
      wrapper.vm.localActions = [
        { id: 1, type: 'local_baserow_create_row', service: {} },
        { type: 'local_baserow_delete_row', service: {} },
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
          { id: 1, type: 'local_baserow_create_row', service: {} },
          { id: 99, type: 'local_baserow_delete_row', service: {} },
        ],
      })

      await wrapper.vm.afterFieldSaved(7)

      // The re-sync picked up the real id: the buffer no longer has an
      // id-less action for the next reconciliation to treat as new.
      expect(wrapper.vm.serverActions.map((a) => a.id)).toEqual([1, 99])
      expect(wrapper.vm.localActions.map((a) => a.id)).toEqual([1, 99])

      wrapper.vm.$client.post.mockClear()
      wrapper.vm.$client.get.mockResolvedValueOnce({
        data: [
          { id: 1, type: 'local_baserow_create_row', service: {} },
          { id: 99, type: 'local_baserow_delete_row', service: {} },
          { id: 100, type: 'local_baserow_create_row', service: {} },
        ],
      })

      // Add a third action and save again on the same mounted instance,
      // without a remount in between.
      wrapper.vm.localActions = [
        ...wrapper.vm.localActions,
        { type: 'local_baserow_create_row', service: {} },
      ]

      await wrapper.vm.afterFieldSaved(7)

      const createCalls = wrapper.vm.$client.post.mock.calls.filter(
        ([url]) => url === 'database/field/7/workflow_actions/'
      )
      // Only the new (third) action is created. A2 (id 99) must not be
      // recreated.
      expect(createCalls).toHaveLength(1)
      expect(createCalls[0][1]).toEqual({ type: 'local_baserow_create_row' })
    })
  })

  describe('formula injection', () => {
    // A field mapping's formula input renders through `InjectedFormulaInput`,
    // which resolves the component from an injected `formulaComponent`. With
    // nothing providing one the injection is undefined and Vue renders a bare
    // comment node, so the mapping showed an empty area instead of an input.
    const mountInjectedInput = async (formWrapper, attrs = {}) =>
      testApp.mount(InjectedFormulaInput, {
        attrs,
        global: { provide: formWrapper.vm.$.provides },
      })

    test('the sub-form provides what InjectedFormulaInput injects', async () => {
      const wrapper = await mountForm({ type: 'button', label: 'Go' })
      const provides = wrapper.vm.$.provides

      expect(provides.formulaComponent).toBeTruthy()
      // The clicked row and what the earlier actions returned. Human readable
      // values are absent from the dispatch context, so `fields` is not one.
      expect(provides.dataProvidersAllowed).toEqual(['row', 'previous_action'])
    })

    test('an action form sees the sub-form context through its own', async () => {
      // The action form provides a context of its own, and everything the
      // sub-form exposes has to keep reaching the inputs under it.
      const wrapper = await mountForm({ type: 'button', label: 'Go' })
      wrapper.vm.localActions = [
        { id: 1, type: 'open_url', url: { formula: "'x'", mode: 'simple' } },
      ]
      await wrapper.vm.$nextTick()

      const context = wrapper.findComponent(ButtonFieldActionForm).vm.$.provides
        .databaseFormulaContext

      expect(context.workflowAction.id).toBe(1)
      expect(context.workflowActions).toHaveLength(1)
      expect(context.fields.map((field) => field.name)).toEqual(['Name'])
    })

    test('InjectedFormulaInput renders a real input under the sub-form', async () => {
      const form = await mountForm({ type: 'button', label: 'Go' })

      const input = await mountInjectedInput(form, {
        modelValue: { formula: "'hi'", mode: 'simple' },
      })

      // Without a provided component this rendered a bare comment node, so
      // both of these were false or empty.
      expect(input.findComponent({ name: 'FormulaInputField' }).exists()).toBe(
        true
      )
      expect(input.html()).not.toBe('<!---->')
    })

    test('an input keeps its explorer context while the list is edited', async () => {
      // The context an input reads is what its explorer is rebuilt from, so a
      // new object on every keystroke rebuilds every mounted input's tree.
      const form = await mountForm({ type: 'button', label: 'Go' })
      const action = {
        id: 1,
        type: 'open_url',
        url: { formula: "'x'", mode: 'simple' },
      }
      form.vm.localActions = [action]
      await form.vm.$nextTick()

      const actionForm = form.findComponent(ButtonFieldActionForm)
      const input = await testApp.mount(InjectedFormulaInput, {
        attrs: { modelValue: { formula: "'hi'", mode: 'simple' } },
        // The action form's own provides sit on a prototype of the sub-form's,
        // which does not survive being handed over as a plain object.
        global: {
          provide: {
            ...form.vm.$.provides,
            ...actionForm.vm.$.provides,
          },
        },
      })
      const databaseInput = input.findComponent({
        name: 'DatabaseFormulaInput',
      })
      const before = databaseInput.vm.applicationContext

      form.vm.localActions = [
        { ...action, url: { formula: "'edited'", mode: 'simple' } },
      ]
      await form.vm.$nextTick()

      expect(databaseInput.vm.applicationContext).toBe(before)
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

    test('a password field is not offered to read from', async () => {
      // Its stored value is the hash, which the dispatch refuses to return.
      const form = await mountForm({ type: 'button', label: 'Go' }, [
        { id: 1, type: 'text', name: 'Name' },
        { id: 2, type: 'password', name: 'Secret' },
      ])

      const input = await mountInjectedInput(form, {
        modelValue: { formula: "'hi'", mode: 'simple' },
      })

      const formulaInput = input.findComponent({ name: 'DatabaseFormulaInput' })
      const dataGroup = formulaInput.vm.nodesHierarchy.find(
        (group) => group.type === 'data'
      )
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
