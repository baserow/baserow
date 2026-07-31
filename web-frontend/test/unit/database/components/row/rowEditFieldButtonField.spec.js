import { vi } from 'vitest'
import { TestApp } from '@baserow/test/helpers/testApp'
import RowEditFieldButtonField from '@baserow/modules/database/components/row/RowEditFieldButtonField'

describe('RowEditFieldButtonField', () => {
  let testApp = null
  let client = null

  beforeEach(() => {
    testApp = new TestApp()
    client = testApp.getApp().$client
    vi.spyOn(client, 'post').mockResolvedValue({ data: [] })
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
    url_formula: { formula: "''", mode: 'simple' },
    has_workflow_actions: true,
    error: null,
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
})
