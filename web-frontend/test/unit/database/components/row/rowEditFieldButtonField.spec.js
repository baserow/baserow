import { vi } from 'vitest'
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
      { row_id: 11 }
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
      applicationContext: { row: { id: 11 }, fields: [field] },
    })
  })
})
