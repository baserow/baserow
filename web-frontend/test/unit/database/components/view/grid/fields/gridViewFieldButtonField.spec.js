import { vi } from 'vitest'
import { TestApp } from '@baserow/test/helpers/testApp'
import GridViewFieldButtonField from '@baserow/modules/database/components/view/grid/fields/GridViewFieldButtonField'

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

  const mountCell = async (props = {}, responseData = {}) => {
    const wrapper = await testApp.mount(GridViewFieldButtonField, {
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
      { row_id: 1 }
    )
  })

  test('a field without actions renders a disabled button and no link', async () => {
    const wrapper = await mountCell({
      field: { ...field, has_workflow_actions: false },
    })

    expect(wrapper.find('a').exists()).toBe(false)
    expect(wrapper.find('button').attributes('disabled')).toBeDefined()
    expect(wrapper.find('button').text()).toBe('Open')
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
      },
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
    await wrapper.vm.$nextTick()

    expect(execute.mock.calls.map((call) => call[0].workflowAction.id)).toEqual(
      [1, 2]
    )
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

  test('a client action that throws leaves the cell clickable', async () => {
    vi.spyOn(openUrlType, 'execute').mockRejectedValue(new Error('nope'))
    const wrapper = await mountCell({}, { client_actions: [openUrlAction] })

    await wrapper.find('button').trigger('click')
    await wrapper.vm.$nextTick()

    expect(wrapper.vm.dispatching).toBe(false)
  })
})
