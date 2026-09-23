import { vi } from 'vitest'
import flushPromises from 'flush-promises'
import { TestApp } from '@baserow/test/helpers/testApp'
import RowCardFieldButtonField from '@baserow/modules/database/components/card/RowCardFieldButtonField'

describe('RowCardFieldButtonField', () => {
  let testApp = null
  let openUrlType = null

  beforeEach(() => {
    testApp = new TestApp()
    openUrlType = testApp._app.$registry.get(
      'databaseWorkflowActionType',
      'open_url'
    )
  })

  afterEach(async () => {
    await testApp.afterEach()
    vi.restoreAllMocks()
  })

  const field = {
    id: 2,
    type: 'button',
    label: 'Open',
    has_workflow_actions: true,
  }

  const mountCell = async (props = {}, responseData = {}, options = {}) => {
    const wrapper = await testApp.mount(RowCardFieldButtonField, {
      propsData: {
        field,
        value: null,
        row: { id: 1, field_1: 'ada' },
        ...props,
      },
      ...options,
    })
    wrapper.vm.$client.post = vi.fn().mockResolvedValue({
      data: { results: [], client_actions: [], ...responseData },
    })
    return wrapper
  }

  test('a field without actions renders a disabled button and no link', async () => {
    const wrapper = await mountCell({
      field: { ...field, has_workflow_actions: false },
    })

    expect(wrapper.find('a').exists()).toBe(false)
    const button = wrapper.find('button')
    expect(button.attributes('disabled')).toBeDefined()
    expect(button.text()).toBe('Open')
    // Nothing to say, so the card keeps the pointer.
    expect(button.element.parentElement.classList).not.toContain(
      'forced-pointer-events-auto'
    )
  })

  test('a user who may not click gets a disabled button that says so', async () => {
    const hasPermission = vi.fn().mockReturnValue(false)
    const wrapper = await mountCell(
      { workspaceId: 9 },
      {},
      { global: { mocks: { $hasPermission: hasPermission } } }
    )

    const button = wrapper.find('button')
    expect(button.attributes('disabled')).toBeDefined()
    expect(hasPermission).toHaveBeenCalledWith(
      'database.table.field.workflow_action.dispatch',
      field,
      9
    )
    // A card takes the pointer away from everything inside it, so the wrapper
    // asks for it back to show the tooltip.
    const wrapperElement = button.element.parentElement
    expect(wrapperElement.classList).toContain('forced-pointer-events-auto')
    expect(wrapperElement.tooltipOptions.value).toBe('buttonField.noPermission')

    await button.trigger('click')

    expect(wrapper.vm.$client.post).not.toHaveBeenCalled()
  })

  test('a field that needs reconfiguring renders a disabled button with a warning', async () => {
    const wrapper = await mountCell({
      field: { ...field, requires_reconfiguration: true },
    })

    const button = wrapper.find('button')
    expect(button.attributes('disabled')).toBeDefined()
    expect(wrapper.find('.iconoir-warning-triangle').exists()).toBe(true)

    await button.trigger('click')

    expect(wrapper.vm.$client.post).not.toHaveBeenCalled()
  })

  test('dispatches on click and runs the returned client actions', async () => {
    const execute = vi.spyOn(openUrlType, 'execute').mockResolvedValue()
    const action = {
      id: 1,
      type: 'open_url',
      url: { formula: "'https://example.com'", mode: 'simple', version: 1 },
      target: 'blank',
    }
    const wrapper = await mountCell({}, { client_actions: [action] })

    await wrapper.find('button').trigger('click')
    await wrapper.vm.$nextTick()

    expect(wrapper.vm.$client.post).toHaveBeenCalledWith(
      `database/field/${field.id}/workflow_actions/dispatch/`,
      { row_id: 1 },
      { omitWebSocketId: true }
    )
    expect(execute).toHaveBeenCalledTimes(1)
    expect(execute.mock.calls[0][0].workflowAction).toEqual(action)
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
    const wrapper = await mountCell()
    wrapper.vm.$client.post = vi
      .fn()
      .mockResolvedValue({ status: 202, data: job })
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
