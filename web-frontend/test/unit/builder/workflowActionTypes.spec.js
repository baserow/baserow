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

  test('groups the Slack action with the Slack integration', () => {
    const slackAction = testApp
      .getRegistry()
      .get('workflowAction', 'slack_write_message')

    expect(slackAction.group.id).toBe('integration-slack_bot')
  })

  test('groups the email action with the SMTP integration', () => {
    const emailAction = testApp
      .getRegistry()
      .get('workflowAction', 'smtp_email')

    expect(emailAction.group.id).toBe('integration-smtp')
  })

  test('groups the HTTP request action under HTTP', () => {
    const httpRequestAction = testApp
      .getRegistry()
      .get('workflowAction', 'http_request')

    expect(httpRequestAction.group.id).toBe('http')
  })

  test('groups file reader actions under Files', () => {
    const registry = testApp.getRegistry()

    expect(
      ['csv_file_reader', 'xls_file_reader'].map(
        (type) => registry.get('workflowAction', type).group.id
      )
    ).toEqual(['files', 'files'])
  })

  test('groups the start workflow action under Workflow', () => {
    const startWorkflowAction = testApp
      .getRegistry()
      .get('workflowAction', 'start_workflow')

    expect(startWorkflowAction.group.id).toBe('workflow')
  })

  test('groups actions without a service under Core', () => {
    const notificationAction = testApp
      .getRegistry()
      .get('workflowAction', 'notification')

    expect(notificationAction.group.id).toBe('core')
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

  test('open page action is in error when custom navigation URL is missing', () => {
    const workflowActionType = testApp
      .getRegistry()
      .get('workflowAction', 'open_page')
    const builder = { id: 1, pages: [] }
    const workflowAction = {
      type: 'open_page',
      navigation_type: 'custom',
      navigate_to_url: { formula: '' },
    }

    expect(
      workflowActionType.isInError(workflowAction, {
        builder,
      })
    ).toBe(true)
    expect(
      workflowActionType.getErrorMessage(workflowAction, {
        builder,
      })
    ).toBe('workflowActionTypes.errorNavigationUrlMissing')

    // Once a custom URL formula is provided, the action is no longer in error.
    workflowAction.navigate_to_url = { formula: "'https://baserow.io'" }

    expect(
      workflowActionType.isInError(workflowAction, {
        builder,
      })
    ).toBe(false)
  })
})
