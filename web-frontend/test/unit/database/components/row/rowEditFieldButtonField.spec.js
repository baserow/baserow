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

  const mountField = (props = {}) =>
    testApp.mount(RowEditFieldButtonField, {
      props: {
        field,
        value: null,
        readOnly: false,
        row: { id: 11 },
        allFieldsInTable: [field],
        ...props,
      },
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

  test('a field without actions renders a disabled button and no link', async () => {
    const wrapper = await mountField({
      field: { ...field, has_workflow_actions: false },
    })

    expect(wrapper.find('a').exists()).toBe(false)
    expect(wrapper.find('button').attributes('disabled')).toBeDefined()
    expect(wrapper.find('button').text()).toBe('Go')
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
})
