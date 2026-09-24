import { vi } from 'vitest'
import flushPromises from 'flush-promises'
import { TestApp } from '@baserow/test/helpers/testApp'
import GridViewFieldButtonField from '@baserow/modules/database/components/view/grid/fields/GridViewFieldButtonField'
import {
  DISPATCH_JOB_DEADLINE_MS,
  DISPATCH_JOB_LAST_CHECK_MS,
} from '@baserow/modules/database/mixins/buttonField'

describe('GridViewFieldButtonField', () => {
  let testApp = null
  let openUrlType = null

  beforeAll(() => {
    testApp = new TestApp()
    openUrlType = testApp._app.$registry.get(
      'databaseWorkflowActionType',
      'open_url'
    )
  })

  afterEach(() => {
    testApp.afterEach()
    vi.restoreAllMocks()
    vi.useRealTimers()
  })

  const field = {
    id: 2,
    type: 'button',
    label: 'Open',
    has_workflow_actions: true,
  }

  const openUrlAction = {
    id: 1,
    type: 'open_url',
    url: { formula: "'https://example.com'", mode: 'simple', version: 1 },
    target: 'blank',
  }

  const mountCell = async (props = {}, responseData = {}, options = {}) => {
    const wrapper = await testApp.mount(GridViewFieldButtonField, {
      ...options,
      propsData: {
        field,
        value: null,
        row: { id: 1, field_1: 'ada' },
        allFieldsInTable: [{ id: 1, type: 'text', name: 'Slug' }, field],
        selected: false,
        readOnly: true,
        storePrefix: 'page/',
        workspaceId: 1,
        ...props,
      },
    })
    // Dispatch goes through the real $client instance shared by the test
    // app, so replace .post with a fresh mock per mount instead of hitting
    // the network mock adapter.
    wrapper.vm.$client.post = vi.fn().mockResolvedValue({
      status: 200,
      data: { results: [], client_actions: [], ...responseData },
    })
    return wrapper
  }

  test('a field with actions renders a button and dispatches on click', async () => {
    const wrapper = await mountCell()

    expect(wrapper.find('button').attributes('disabled')).toBeUndefined()
    expect(wrapper.find('button').text()).toBe('Open')

    await wrapper.find('button').trigger('click')

    expect(wrapper.vm.$client.post).toHaveBeenCalledWith(
      `database/field/${field.id}/workflow_actions/dispatch/`,
      { row_id: 1 },
      { omitWebSocketId: true }
    )
  })

  test('the selected cell is outlined like every other field', async () => {
    // The grid only mounts this component for the selected cell, and the
    // outline comes from the `active` class.
    const wrapper = await mountCell({ selected: true })

    expect(wrapper.find('.grid-view__cell').classes()).toContain('active')
  })

  test('a user who may not click gets a disabled button', async () => {
    const hasPermission = vi.fn().mockReturnValue(false)
    const wrapper = await mountCell(
      { workspaceId: 9 },
      {},
      { global: { mocks: { $hasPermission: hasPermission } } }
    )

    expect(wrapper.find('button').attributes('disabled')).toBeDefined()
    // Asked of the field, which is all a cell has, in the field's workspace.
    expect(hasPermission).toHaveBeenCalledWith(
      'database.table.field.workflow_action.dispatch',
      field,
      9
    )

    await wrapper.find('button').trigger('click')

    expect(wrapper.vm.$client.post).not.toHaveBeenCalled()
  })

  test('a field without actions renders a disabled button and no link', async () => {
    const wrapper = await mountCell({
      field: { ...field, has_workflow_actions: false },
    })

    expect(wrapper.find('a').exists()).toBe(false)
    expect(wrapper.find('button').attributes('disabled')).toBeDefined()
    expect(wrapper.find('button').text()).toBe('Open')
  })

  test('a field that needs reconfiguring renders a disabled button with a warning', async () => {
    const wrapper = await mountCell({
      field: { ...field, requires_reconfiguration: true },
    })

    const button = wrapper.find('button')
    expect(button.attributes('disabled')).toBeDefined()
    expect(button.text()).toBe('Open')
    expect(wrapper.find('.iconoir-warning-triangle').exists()).toBe(true)
    // Nothing in between, or the button's max width shrinks with the label.
    expect(wrapper.find('.grid-field-button > button').exists()).toBe(true)

    await button.trigger('click')

    expect(wrapper.vm.$client.post).not.toHaveBeenCalled()
  })

  test('runs the returned client actions after the response', async () => {
    const execute = vi.spyOn(openUrlType, 'execute').mockResolvedValue()
    const wrapper = await mountCell({}, { client_actions: [openUrlAction] })

    await wrapper.find('button').trigger('click')
    await wrapper.vm.$nextTick()

    expect(execute).toHaveBeenCalledTimes(1)
    expect(execute).toHaveBeenCalledWith({
      workflowAction: openUrlAction,
      applicationContext: {
        row: { id: 1, field_1: 'ada' },
        fields: [{ id: 1, type: 'text', name: 'Slug' }, field],
        previousActionResults: {},
      },
    })
  })

  test('a client action sees the row as it was at click time', async () => {
    // The dispatch takes its own realtime broadcast, so a row action can
    // update the cell's row while the request is still in flight.
    const execute = vi.spyOn(openUrlType, 'execute').mockResolvedValue()
    const wrapper = await mountCell({}, { client_actions: [openUrlAction] })
    wrapper.vm.$client.post = vi.fn().mockImplementation(async () => {
      wrapper.vm.row.field_1 = 'updated by an earlier action'
      return { data: { results: [], client_actions: [openUrlAction] } }
    })

    await wrapper.find('button').trigger('click')
    await flushPromises()

    expect(execute.mock.calls[0][0].applicationContext.row).toEqual({
      id: 1,
      field_1: 'ada',
    })
  })

  test('runs the client actions in the order the backend returned them', async () => {
    const execute = vi.spyOn(openUrlType, 'execute').mockResolvedValue()
    const second = { ...openUrlAction, id: 2, target: 'self' }
    const wrapper = await mountCell(
      {},
      { client_actions: [openUrlAction, second] }
    )

    await wrapper.find('button').trigger('click')
    await flushPromises()

    expect(execute.mock.calls.map((call) => call[0].workflowAction.id)).toEqual(
      [1, 2]
    )
  })

  test('a client action that could not run stops the ones after it', async () => {
    // The real `execute` here, not a mock: a refused URL has to report itself
    // as not run, or the action after it navigates away and takes the message
    // with it.
    const open = vi.spyOn(window, 'open').mockImplementation(() => null)
    const refused = {
      ...openUrlAction,
      url: { formula: "'javascript:alert(1)'", mode: 'simple', version: 1 },
    }
    const second = { ...openUrlAction, id: 2 }
    const wrapper = await mountCell({}, { client_actions: [refused, second] })
    const dispatch = vi.spyOn(testApp.store, 'dispatch')

    await wrapper.find('button').trigger('click')
    await flushPromises()

    expect(dispatch).toHaveBeenCalledWith(
      'toast/error',
      expect.objectContaining({
        title: 'openUrlWorkflowAction.invalidUrlTitle',
      })
    )
    expect(open).not.toHaveBeenCalled()
  })

  test('waits for a client action to settle before running the next one', async () => {
    // `open_url` with target `self` navigates the document away. Firing the
    // next action at a navigating page is exactly what awaiting each one
    // prevents, so an unawaited loop has to fail here.
    let release
    const firstSettles = new Promise((resolve) => {
      release = resolve
    })
    const execute = vi
      .spyOn(openUrlType, 'execute')
      .mockImplementationOnce(() => firstSettles)
      .mockResolvedValue()
    const second = { ...openUrlAction, id: 2, target: 'self' }
    const wrapper = await mountCell(
      {},
      { client_actions: [openUrlAction, second] }
    )

    await wrapper.find('button').trigger('click')
    await flushPromises()

    expect(execute).toHaveBeenCalledTimes(1)
    expect(wrapper.vm.dispatching).toBe(true)

    release()
    await flushPromises()

    expect(execute).toHaveBeenCalledTimes(2)
    expect(execute.mock.calls[1][0].workflowAction.id).toBe(2)
    expect(wrapper.vm.dispatching).toBe(false)
  })

  test('a failed dispatch runs no client action and leaves the cell clickable', async () => {
    const execute = vi.spyOn(openUrlType, 'execute').mockResolvedValue()
    const wrapper = await mountCell()
    wrapper.vm.$client.post.mockRejectedValueOnce(new Error('nope'))

    await wrapper.find('button').trigger('click')
    await wrapper.vm.$nextTick()

    expect(execute).not.toHaveBeenCalled()
    expect(wrapper.vm.dispatching).toBe(false)
  })

  test('a second cell for the same row shows the dispatch in flight', async () => {
    // The grid swaps an unselected cell for its own component on the first
    // click, so a flag held by the component that started the request would be
    // thrown away by that remount.
    let release
    const held = new Promise((resolve) => {
      release = resolve
    })
    const first = await mountCell()
    const second = await mountCell()
    // `$client` is shared by the test app, so the held mock has to go on after
    // both mounts or the second one replaces it.
    first.vm.$client.post = vi.fn().mockImplementation(async () => {
      await held
      return { data: { results: [], client_actions: [] } }
    })

    first.find('button').trigger('click')
    await flushPromises()

    expect(second.vm.dispatching).toBe(true)

    release()
    await flushPromises()

    expect(second.vm.dispatching).toBe(false)
  })

  test('a client action that throws leaves the cell clickable', async () => {
    vi.spyOn(openUrlType, 'execute').mockRejectedValue(new Error('nope'))
    const wrapper = await mountCell({}, { client_actions: [openUrlAction] })

    await wrapper.find('button').trigger('click')
    await wrapper.vm.$nextTick()

    expect(wrapper.vm.dispatching).toBe(false)
  })

  const acceptedJob = () => ({
    id: 7,
    type: 'button_field_dispatch',
    state: 'pending',
    progress_percentage: 0,
    human_readable_error: '',
    results: null,
    client_actions: null,
  })

  const finishJob = async (wrapper, values) => {
    const store = wrapper.vm.$store
    const job = store.getters['job/get'](acceptedJob().id)
    await store.dispatch('job/forceUpdate', {
      job,
      data: { ...acceptedJob(), ...values },
    })
    await flushPromises()
  }

  test('an accepted click waits on its job and then runs the client actions', async () => {
    const execute = vi.spyOn(openUrlType, 'execute').mockResolvedValue()
    const wrapper = await mountCell()
    wrapper.vm.$client.post = vi
      .fn()
      .mockResolvedValue({ status: 202, data: acceptedJob() })

    await wrapper.find('button').trigger('click')
    await flushPromises()

    // Still waiting: the spinner stays and nothing has run.
    expect(wrapper.vm.dispatching).toBe(true)
    expect(execute).not.toHaveBeenCalled()
    expect(wrapper.vm.$store.getters['job/get'](acceptedJob().id)).toBeTruthy()

    await finishJob(wrapper, {
      state: 'finished',
      results: [
        {
          workflow_action_id: 3,
          order: 1,
          position: 1,
          status: 'completed',
          data: { id: 99 },
          field_names: {},
        },
      ],
      client_actions: [{ ...openUrlAction, position: 2 }],
    })

    expect(wrapper.vm.dispatching).toBe(false)
    expect(execute).toHaveBeenCalledTimes(1)
    expect(
      execute.mock.calls[0][0].applicationContext.previousActionResults
    ).toEqual({
      3: { data: { id: 99 }, fieldNames: {}, order: 1, position: 1 },
    })
    // Settled, so the store no longer polls it.
    expect(wrapper.vm.$store.getters['job/get'](acceptedJob().id)).toBeFalsy()
  })

  test('a failed job shows its message and clears the spinner', async () => {
    const execute = vi.spyOn(openUrlType, 'execute').mockResolvedValue()
    const wrapper = await mountCell()
    wrapper.vm.$client.post = vi
      .fn()
      .mockResolvedValue({ status: 202, data: acceptedJob() })
    const toast = vi.spyOn(wrapper.vm.$store, 'dispatch')

    await wrapper.find('button').trigger('click')
    await flushPromises()
    await finishJob(wrapper, {
      state: 'failed',
      human_readable_error:
        'Action 1 ran before action 2 failed: No table selected',
    })

    expect(wrapper.vm.dispatching).toBe(false)
    expect(execute).not.toHaveBeenCalled()
    expect(toast).toHaveBeenCalledWith('toast/error', {
      title: 'buttonField.dispatchErrorTitle',
      message: 'Action 1 ran before action 2 failed: No table selected',
    })
  })

  test('the spinner survives a remount while the job polls', async () => {
    const wrapper = await mountCell()
    wrapper.vm.$client.post = vi
      .fn()
      .mockResolvedValue({ status: 202, data: acceptedJob() })

    await wrapper.find('button').trigger('click')
    await flushPromises()
    // The grid swaps the cell component on selection; the flag is keyed by
    // field and row outside the component, so the new one still spins.
    const remounted = await mountCell({ selected: true })

    expect(remounted.vm.dispatching).toBe(true)

    await finishJob(wrapper, {
      state: 'finished',
      results: [],
      client_actions: [],
    })

    expect(remounted.vm.dispatching).toBe(false)
  })

  test('a job that is already finished on the 202 runs its client actions without polling', async () => {
    const execute = vi.spyOn(openUrlType, 'execute').mockResolvedValue()
    const wrapper = await mountCell()
    wrapper.vm.$client.post = vi.fn().mockResolvedValue({
      status: 202,
      data: {
        ...acceptedJob(),
        state: 'finished',
        results: [],
        client_actions: [openUrlAction],
      },
    })

    await wrapper.find('button').trigger('click')
    await flushPromises()

    expect(execute).toHaveBeenCalledTimes(1)
    expect(wrapper.vm.dispatching).toBe(false)
  })

  // Answers the one fetch of the click's job the deadline makes, and leaves
  // every other request, the job store's own polls included, to the client.
  const answerJobFetch = (wrapper, job) => {
    const client = wrapper.vm.$client
    const originalGet = client.get
    const get = vi.fn((url, ...args) =>
      url === `/jobs/${acceptedJob().id}/`
        ? Promise.resolve({ data: job })
        : originalGet.call(client, url, ...args)
    )
    client.get = get
    return get
  }

  test('a click gives up on a job that never reaches a final state', async () => {
    // Only the timer the deadline itself uses is faked, so the promise
    // machinery the dispatch, the store and `flushPromises` all rely on
    // keeps working as normal.
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
    const execute = vi.spyOn(openUrlType, 'execute').mockResolvedValue()
    const wrapper = await mountCell()
    wrapper.vm.$client.post = vi
      .fn()
      .mockResolvedValue({ status: 202, data: acceptedJob() })
    const get = answerJobFetch(wrapper, acceptedJob())
    const toast = vi.spyOn(wrapper.vm.$store, 'dispatch')

    await wrapper.find('button').trigger('click')
    await flushPromises()

    expect(wrapper.vm.dispatching).toBe(true)

    await vi.advanceTimersByTimeAsync(DISPATCH_JOB_DEADLINE_MS + 1)
    await flushPromises()

    expect(get).toHaveBeenCalledWith(`/jobs/${acceptedJob().id}/`)
    expect(wrapper.vm.dispatching).toBe(false)
    expect(execute).not.toHaveBeenCalled()
    expect(toast).toHaveBeenCalledWith('toast/error', {
      title: 'buttonField.stillRunningTitle',
      message: 'buttonField.stillRunningMessage',
    })
  })

  test('a job the poller stopped watching still runs its client actions if it finished by the deadline', async () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
    const execute = vi.spyOn(openUrlType, 'execute').mockResolvedValue()
    const wrapper = await mountCell()
    wrapper.vm.$client.post = vi
      .fn()
      .mockResolvedValue({ status: 202, data: acceptedJob() })
    answerJobFetch(wrapper, {
      ...acceptedJob(),
      state: 'finished',
      results: [],
      client_actions: [openUrlAction],
    })
    const toast = vi.spyOn(wrapper.vm.$store, 'dispatch')

    await wrapper.find('button').trigger('click')
    await flushPromises()
    await vi.advanceTimersByTimeAsync(DISPATCH_JOB_DEADLINE_MS + 1)
    await flushPromises()

    expect(wrapper.vm.dispatching).toBe(false)
    expect(execute).toHaveBeenCalledTimes(1)
    expect(toast).not.toHaveBeenCalledWith('toast/error', expect.anything())
  })

  test('a last check that never answers still clears the spinner', async () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
    const wrapper = await mountCell()
    wrapper.vm.$client.post = vi
      .fn()
      .mockResolvedValue({ status: 202, data: acceptedJob() })
    const client = wrapper.vm.$client
    const originalGet = client.get
    client.get = vi.fn((url, ...args) =>
      url === `/jobs/${acceptedJob().id}/`
        ? new Promise(() => {})
        : originalGet.call(client, url, ...args)
    )
    const toast = vi.spyOn(wrapper.vm.$store, 'dispatch')

    await wrapper.find('button').trigger('click')
    await flushPromises()
    await vi.advanceTimersByTimeAsync(DISPATCH_JOB_DEADLINE_MS + 1)
    await flushPromises()

    expect(wrapper.vm.dispatching).toBe(true)

    await vi.advanceTimersByTimeAsync(DISPATCH_JOB_LAST_CHECK_MS + 1)
    await flushPromises()

    expect(wrapper.vm.dispatching).toBe(false)
    expect(toast).toHaveBeenCalledWith('toast/error', {
      title: 'buttonField.stillRunningTitle',
      message: 'buttonField.stillRunningMessage',
    })
  })
})
