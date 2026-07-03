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

  test('open page action is in error when saved page parameters are outdated', () => {
    const workflowActionType = testApp
      .getRegistry()
      .get('workflowAction', 'open_page')
    const builder = {
      id: 1,
      pages: [
        {
          id: 1,
          shared: false,
          order: 1,
          path: '/',
          path_params: [],
        },
        {
          id: 2,
          shared: false,
          order: 2,
          path: '/details/:slug',
          path_params: [{ name: 'slug', type: 'text' }],
        },
      ],
    }
    const workflowAction = {
      type: 'open_page',
      navigation_type: 'page',
      navigate_to_page_id: 2,
      page_parameters: [],
    }

    expect(
      workflowActionType.isInError(workflowAction, {
        builder,
      })
    ).toBe(true)
  })

  test('open page action is in error when a required page parameter is empty', () => {
    const workflowActionType = testApp
      .getRegistry()
      .get('workflowAction', 'open_page')
    const builder = {
      id: 1,
      pages: [
        {
          id: 1,
          shared: false,
          order: 1,
          path: '/',
          path_params: [],
        },
        {
          id: 2,
          shared: false,
          order: 2,
          path: '/details/:id',
          path_params: [{ name: 'id', type: 'numeric' }],
        },
      ],
    }
    const workflowAction = {
      type: 'open_page',
      navigation_type: 'page',
      navigate_to_page_id: 2,
      page_parameters: [{ name: 'id', value: {} }],
    }

    expect(
      workflowActionType.isInError(workflowAction, {
        builder,
      })
    ).toBe(true)

    workflowAction.page_parameters = [{ name: 'id', value: { formula: '' } }]

    expect(
      workflowActionType.isInError(workflowAction, {
        builder,
      })
    ).toBe(true)
  })
})
