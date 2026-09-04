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
    expect(slackAction.group.image).toBeDefined()
    expect(slackAction.icon).toBe('iconoir-message-text')
    expect(slackAction.iconColor).toBe('darker-pink')
    expect(slackAction.image).toBeUndefined()
  })

  test('groups the email action with the SMTP integration', () => {
    const emailAction = testApp
      .getRegistry()
      .get('workflowAction', 'smtp_email')

    expect(emailAction.group.id).toBe('integration-smtp')
    expect(emailAction.iconColor).toBe('muted-red')
  })

  test('groups the HTTP request action under HTTP', () => {
    const httpRequestAction = testApp
      .getRegistry()
      .get('workflowAction', 'http_request')

    expect(httpRequestAction.group.id).toBe('http')
    expect(httpRequestAction.iconColor).toBe('muted-cyan')
  })

  test('groups file reader actions under Files', () => {
    const registry = testApp.getRegistry()

    expect(
      ['csv_file_reader', 'xls_file_reader'].map(
        (type) => registry.get('workflowAction', type).group.id
      )
    ).toEqual(['files', 'files'])
    expect(registry.get('workflowAction', 'csv_file_reader').iconColor).toBe(
      'muted-yellow'
    )
  })

  test('groups the start workflow action under Workflow', () => {
    const startWorkflowAction = testApp
      .getRegistry()
      .get('workflowAction', 'start_workflow')

    expect(startWorkflowAction.group.id).toBe('workflow')
    expect(startWorkflowAction.iconColor).toBe('muted-purple')
  })

  test('groups actions without a service under Core', () => {
    const notificationAction = testApp
      .getRegistry()
      .get('workflowAction', 'notification')

    expect(notificationAction.group.id).toBe('core')
    expect(notificationAction.iconColor).toBe('muted-green')
    expect(notificationAction.description).toBe(
      'workflowActionTypes.notificationDescription'
    )
  })

  test('uses service descriptions for service workflow actions', () => {
    const createRowAction = testApp
      .getRegistry()
      .get('workflowAction', 'create_row')

    expect(createRowAction.description).toBe(
      'serviceType.localBaserowCreateRowDescription'
    )
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

  test('service-backed action flags its trashed integration as in-error', () => {
    const workflowActionType = testApp
      .getRegistry()
      .get('workflowAction', 'create_row')

    // The builder's only live integration is id 5; id 41 has been trashed and is
    // therefore no longer present on the builder.
    const builder = {
      id: 1,
      integrations: [{ id: 5, type: 'local_baserow' }],
    }

    // Live integration + a table selected → not in error.
    expect(
      workflowActionType.getErrorMessage(
        { type: 'create_row', service: { integration_id: 5, table_id: 99 } },
        { builder, mode: 'editing' }
      )
    ).toBe(null)

    // Integration 41 is absent (trashed) → the action is misconfigured.
    const trashedAction = {
      type: 'create_row',
      service: { integration_id: 41, table_id: 99 },
    }
    expect(
      workflowActionType.getErrorMessage(trashedAction, {
        builder,
        mode: 'editing',
      })
    ).toBe('serviceType.errorMisconfiguredIntegration')
    expect(
      workflowActionType.isInError(trashedAction, { builder, mode: 'editing' })
    ).toBe(true)
  })

  test('integration check is skipped outside the editor', () => {
    const workflowActionType = testApp
      .getRegistry()
      .get('workflowAction', 'create_row')

    // Preview/public mode never loads the builder's integrations, so a
    // configured action must not be flagged as misconfigured there (it would
    // hide its element from the rendered page).
    const builder = { id: 1, integrations: [] }
    const action = {
      type: 'create_row',
      service: { integration_id: 41, table_id: 99 },
    }

    for (const mode of ['preview', 'public']) {
      expect(
        workflowActionType.getErrorMessage(action, { builder, mode })
      ).toBe(null)
      expect(workflowActionType.isInError(action, { builder, mode })).toBe(
        false
      )
    }
  })
})
