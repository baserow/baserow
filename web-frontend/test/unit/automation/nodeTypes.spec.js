import { TestApp } from '@baserow/test/helpers/testApp'

describe('Automation node types', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  test('orders workflow action nodes in the add node menu', () => {
    const nodeTypes = testApp
      .getRegistry()
      .getOrderedList('node')
      .filter((nodeType) => nodeType.isWorkflowAction)
      .map((type) => type.getType())

    expect(nodeTypes).toEqual([
      'local_baserow_create_row',
      'local_baserow_create_rows',
      'local_baserow_update_row',
      'local_baserow_update_rows',
      'local_baserow_delete_row',
      'local_baserow_get_row',
      'local_baserow_list_rows',
      'local_baserow_aggregate_rows',
      'start_workflow',
      'http_request',
      'smtp_email',
      'code',
      'iterator',
      'ai_agent',
      'router',
      'csv_file_reader',
      'xls_file_reader',
      'slack_write_message',
    ])
  })

  test('groups HTTP trigger and request nodes under HTTP', () => {
    const registry = testApp.getRegistry()

    expect(
      ['http_trigger', 'http_request'].map(
        (type) => registry.get('node', type).group.id
      )
    ).toEqual(['http', 'http'])
  })

  test('groups file reader nodes under Files', () => {
    const registry = testApp.getRegistry()

    expect(
      ['csv_file_reader', 'xls_file_reader'].map(
        (type) => registry.get('node', type).group.id
      )
    ).toEqual(['files', 'files'])
  })

  test('groups workflow nodes under Workflow', () => {
    const registry = testApp.getRegistry()

    expect(
      ['start_workflow', 'iterator', 'router'].map(
        (type) => registry.get('node', type).group.id
      )
    ).toEqual(['workflow', 'workflow', 'workflow'])
  })
})
