import { vi } from 'vitest'
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

  const mountCell = async (props = {}, responseData = {}) => {
    const wrapper = await testApp.mount(RowCardFieldButtonField, {
      propsData: {
        field,
        value: null,
        row: { id: 1, field_1: 'ada' },
        ...props,
      },
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
    expect(wrapper.find('button').attributes('disabled')).toBeDefined()
    expect(wrapper.find('button').text()).toBe('Open')
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
      { row_id: 1 }
    )
    expect(execute).toHaveBeenCalledTimes(1)
    expect(execute.mock.calls[0][0].workflowAction).toEqual(action)
  })
})
