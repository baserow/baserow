import { TestApp } from '@baserow/test/helpers/testApp'

describe('Builder workflow action types', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  test('orders workflow actions in the add action menu', () => {
    const workflowActionTypes = testApp
      .getRegistry()
      .getOrderedList('workflowAction')
      .map((type) => type.getType())

    expect(workflowActionTypes).toEqual([
      'notification',
      'open_page',
      'logout',
      'refresh_data_source',
      'create_row',
      'local_baserow_create_rows',
      'update_row',
      'local_baserow_update_rows',
      'delete_row',
      'start_workflow',
      'http_request',
      'smtp_email',
      'code',
      'ai_agent',
      'csv_file_reader',
      'xls_file_reader',
      'slack_write_message',
    ])
  })
})
