import { vi } from 'vitest'
import flushPromises from 'flush-promises'
import { TestApp } from '@baserow/test/helpers/testApp'
import RowEditFieldButtonField from '@baserow/modules/database/components/row/RowEditFieldButtonField'

describe('RowEditFieldButtonField', () => {
  let testApp = null
  let client = null
  let openUrlType = null

  beforeEach(() => {
    testApp = new TestApp()
    client = testApp.getApp().$client
    openUrlType = testApp._app.$registry.get(
      'databaseWorkflowActionType',
      'open_url'
    )
    vi.spyOn(client, 'post').mockResolvedValue({
      data: { results: [], client_actions: [] },
    })
  })

  afterEach(async () => {
    await testApp.afterEach()
    vi.restoreAllMocks()
  })

  const field = {
    id: 3,
    table_id: 1,
    name: 'Go',
    type: 'button',
    label: 'Go',
    has_workflow_actions: true,
  }

  const mountField = (props = {}, options = {}) =>
    testApp.mount(RowEditFieldButtonField, {
      props: {
        field,
        value: null,
        readOnly: false,
        row: { id: 11 },
        allFieldsInTable: [field],
        ...props,
      },
      ...options,
    })

  test('the dispatch button runs the actions for a created row', async () => {
    const wrapper = await mountField()

    const button = wrapper.find('button')
    expect(button.attributes('disabled')).toBeUndefined()

    await button.trigger('click')

    expect(client.post).toHaveBeenCalledWith(
      'database/field/3/workflow_actions/dispatch/',
      { row_id: 11 },
      { omitWebSocketId: true }
    )
  })

  test('the dispatch button is inert in the row create modal', async () => {
    // `RowCreateModal` renders every visible field, but there is no row yet:
    // dispatching would post `row_id: undefined` and get a 400 back.
    const wrapper = await mountField({ row: {}, rowIsCreated: false })

    const button = wrapper.find('button')
    expect(button.attributes('disabled')).toBeDefined()

    await button.trigger('click')

    expect(client.post).not.toHaveBeenCalled()
  })

  test('a user who may not click gets a disabled button that says so', async () => {
    const hasPermission = vi.fn().mockReturnValue(false)
    const wrapper = await mountField(
      { workspaceId: 9 },
      { global: { mocks: { $hasPermission: hasPermission } } }
    )

    const button = wrapper.find('button')
    expect(button.attributes('disabled')).toBeDefined()
    expect(hasPermission).toHaveBeenCalledWith(
      'database.table.field.workflow_action.dispatch',
      field,
      9
    )
    // A disabled button fires no mouse events, so the wrapper carries the
    // tooltip.
    expect(button.element.parentElement.tooltipOptions.value).toBe(
      'buttonField.noPermission'
    )

    await button.trigger('click')

    expect(client.post).not.toHaveBeenCalled()
  })

  test('a field without actions renders a disabled button and no link', async () => {
    const wrapper = await mountField({
      field: { ...field, has_workflow_actions: false },
    })

    expect(wrapper.find('a').exists()).toBe(false)
    expect(wrapper.find('button').attributes('disabled')).toBeDefined()
    expect(wrapper.find('button').text()).toBe('Go')
  })

  test('a field that needs reconfiguring renders a disabled button with a warning', async () => {
    const wrapper = await mountField({
      field: { ...field, requires_reconfiguration: true },
    })

    const button = wrapper.find('button')
    expect(button.attributes('disabled')).toBeDefined()
    expect(wrapper.find('.iconoir-warning-triangle').exists()).toBe(true)

    await button.trigger('click')

    expect(client.post).not.toHaveBeenCalled()
  })

  test('runs the returned client actions after the response', async () => {
    const execute = vi.spyOn(openUrlType, 'execute').mockResolvedValue()
    const action = {
      id: 1,
      type: 'open_url',
      url: { formula: "'https://example.com'", mode: 'simple', version: 1 },
      target: 'self',
    }
    client.post.mockResolvedValue({
      data: { results: [], client_actions: [action] },
    })
    const wrapper = await mountField()

    await wrapper.find('button').trigger('click')
    await wrapper.vm.$nextTick()

    expect(execute).toHaveBeenCalledWith({
      workflowAction: action,
      applicationContext: {
        row: { id: 11 },
        fields: [field],
        previousActionResults: {},
      },
    })
  })

  test('a client action is given what the server actions returned', async () => {
    const execute = vi.spyOn(openUrlType, 'execute').mockResolvedValue()
    const action = {
      id: 2,
      type: 'open_url',
      url: { formula: "'https://example.com'", mode: 'simple', version: 1 },
      target: 'self',
    }
    client.post.mockResolvedValue({
      data: {
        results: [
          {
            workflow_action_id: 1,
            status: 'completed',
            data: { id: 99, Name: 'Ada' },
            field_names: { field_10: 'Name' },
          },
        ],
        client_actions: [action],
      },
    })
    const wrapper = await mountField()

    await wrapper.find('button').trigger('click')
    await wrapper.vm.$nextTick()

    // Keyed as a string, the way a formula path carries the id.
    expect(
      execute.mock.calls[0][0].applicationContext.previousActionResults
    ).toEqual({
      1: { data: { id: 99, Name: 'Ada' }, fieldNames: { field_10: 'Name' } },
    })
  })

  test('a client action cannot read a result from an action ordered after it', async () => {
    // Client actions always run last, so every server result is in the
    // response. Only the ones the clicker put before it may be read, or the
    // browser would resolve what the dispatch refuses.
    const execute = vi.spyOn(openUrlType, 'execute').mockResolvedValue()
    const action = {
      id: 2,
      order: 1,
      type: 'open_url',
      url: { formula: "'https://example.com'", mode: 'simple', version: 1 },
      target: 'self',
    }
    client.post.mockResolvedValue({
      data: {
        results: [
          {
            workflow_action_id: 1,
            order: 2,
            status: 'completed',
            data: { id: 99, Name: 'Ada' },
            field_names: { field_10: 'Name' },
          },
        ],
        client_actions: [action],
      },
    })
    const wrapper = await mountField()

    await wrapper.find('button').trigger('click')
    await wrapper.vm.$nextTick()

    expect(
      execute.mock.calls[0][0].applicationContext.previousActionResults
    ).toEqual({})
  })

  test('a client action reads a result that shares its order', async () => {
    // Two actions created at once can be given the same `order`, which the
    // dispatch then breaks by id. Comparing the orders alone would drop the
    // earlier result, and the client action would fail on a valid reference.
    const execute = vi.spyOn(openUrlType, 'execute').mockResolvedValue()
    const action = {
      id: 2,
      order: 1,
      position: 2,
      type: 'open_url',
      url: { formula: "'https://example.com'", mode: 'simple', version: 1 },
      target: 'self',
    }
    client.post.mockResolvedValue({
      data: {
        results: [
          {
            workflow_action_id: 1,
            order: 1,
            position: 1,
            status: 'completed',
            data: { id: 99, Name: 'Ada' },
            field_names: { field_10: 'Name' },
          },
        ],
        client_actions: [action],
      },
    })
    const wrapper = await mountField()

    await wrapper.find('button').trigger('click')
    await wrapper.vm.$nextTick()

    expect(
      execute.mock.calls[0][0].applicationContext.previousActionResults
    ).toEqual({
      1: {
        data: { id: 99, Name: 'Ada' },
        fieldNames: { field_10: 'Name' },
        order: 1,
        position: 1,
      },
    })
  })

  test('a failed dispatch raises a toast of its own', async () => {
    // A network failure would otherwise be thrown out of an unawaited click
    // handler, and the click would look like it did nothing.
    client.post.mockRejectedValue(new Error('boom'))
    const dispatch = vi.spyOn(testApp.store, 'dispatch')
    const wrapper = await mountField()

    await wrapper.find('button').trigger('click')
    await flushPromises()

    // The test app has no translations loaded, so `$t` hands back the keys.
    expect(dispatch).toHaveBeenCalledWith('toast/error', {
      title: 'buttonField.dispatchErrorTitle',
      message: 'buttonField.dispatchErrorMessage',
    })
  })

  test('a handled API error is reported through the error handler', async () => {
    // A handled error already carries the backend's message, so the generic
    // toast must not replace it or be raised alongside it.
    const notifyIf = vi.fn()
    client.post.mockRejectedValue(
      Object.assign(new Error('boom'), { handler: { notifyIf } })
    )
    const dispatch = vi.spyOn(testApp.store, 'dispatch')
    const wrapper = await mountField()

    await wrapper.find('button').trigger('click')
    await flushPromises()

    expect(notifyIf).toHaveBeenCalledWith('workflowAction')
    expect(dispatch).not.toHaveBeenCalledWith('toast/error', expect.anything())
  })

  test('a refused click says so, rather than looking like nothing happened', async () => {
    // The shared error handler stays quiet on a 429: it only speaks for
    // Baserow API errors, network errors and 404s. Without this the rate limit
    // would refuse a click with no sign of it on screen.
    const notifyIf = vi.fn()
    client.post.mockRejectedValue(
      Object.assign(new Error('boom'), {
        handler: { notifyIf, isTooManyRequests: () => true },
      })
    )
    const dispatch = vi.spyOn(testApp.store, 'dispatch')
    const wrapper = await mountField()

    await wrapper.find('button').trigger('click')
    await flushPromises()

    expect(dispatch).toHaveBeenCalledWith('toast/error', {
      title: 'buttonField.rateLimitedTitle',
      message: 'buttonField.rateLimitedMessage',
    })
    expect(notifyIf).not.toHaveBeenCalled()
  })

  test('a failed dispatch leaves the button clickable', async () => {
    client.post.mockRejectedValue(new Error('boom'))
    const wrapper = await mountField()

    await wrapper.find('button').trigger('click')
    await flushPromises()
    await wrapper.find('button').trigger('click')
    await flushPromises()

    expect(client.post).toHaveBeenCalledTimes(2)
  })

  test('no client action runs when the dispatch failed', async () => {
    const execute = vi.spyOn(openUrlType, 'execute').mockResolvedValue()
    client.post.mockRejectedValue(new Error('boom'))
    const wrapper = await mountField()

    await wrapper.find('button').trigger('click')
    await flushPromises()

    expect(execute).not.toHaveBeenCalled()
  })

  test('an accepted click waits on its job and then runs the client actions', async () => {
    const execute = vi.spyOn(openUrlType, 'execute').mockResolvedValue()
    const job = {
      id: 7,
      type: 'button_field_dispatch',
      state: 'pending',
      progress_percentage: 0,
      human_readable_error: '',
      results: null,
      client_actions: null,
    }
    const action = {
      id: 1,
      type: 'open_url',
      url: { formula: "'https://example.com'", mode: 'simple', version: 1 },
      target: 'self',
    }
    client.post.mockResolvedValue({ status: 202, data: job })
    const wrapper = await mountField()
    const store = wrapper.vm.$store

    await wrapper.find('button').trigger('click')
    await flushPromises()

    // Still waiting: the spinner stays and nothing has run.
    expect(wrapper.vm.dispatching).toBe(true)
    expect(wrapper.find('button').classes()).toContain('button--loading')
    expect(execute).not.toHaveBeenCalled()
    expect(store.getters['job/get'](job.id)).toBeTruthy()

    await store.dispatch('job/forceUpdate', {
      job: store.getters['job/get'](job.id),
      data: {
        ...job,
        state: 'finished',
        results: [],
        client_actions: [action],
      },
    })
    await flushPromises()

    expect(wrapper.vm.dispatching).toBe(false)
    expect(wrapper.find('button').classes()).not.toContain('button--loading')
    expect(execute).toHaveBeenCalledTimes(1)
    expect(execute.mock.calls[0][0].workflowAction).toEqual(action)
  })
})
