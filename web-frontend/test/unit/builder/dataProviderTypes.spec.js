import { TestApp } from '@baserow/test/helpers/testApp'

describe('Builder data provider types', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  test('previous action provider resolves list workflow action results', () => {
    const dataProvider = testApp
      .getRegistry()
      .get('builderDataProvider', 'previous_action')

    const workflowAction = {
      id: 10,
      type: 'csv_file_reader',
      service: {
        id: 20,
        type: 'csv_file_reader',
        schema: {
          items: {
            properties: {
              Email: { title: 'Email' },
            },
          },
        },
      },
    }
    const page = { id: 1, workflowActions: [workflowAction] }
    const applicationContext = {
      page,
      previousActionResults: {
        10: {
          results: [{ Email: 'a@example.com' }, { Email: 'b@example.com' }],
          has_next_page: false,
        },
      },
    }

    expect(dataProvider.getDataChunk(applicationContext, ['10'])).toEqual([
      { Email: 'a@example.com' },
      { Email: 'b@example.com' },
    ])
    expect(dataProvider.getDataChunk(applicationContext, ['10', '1'])).toEqual({
      Email: 'b@example.com',
    })
    expect(
      dataProvider.getDataChunk(applicationContext, ['10', '*', 'Email'])
    ).toEqual(['a@example.com', 'b@example.com'])
  })

  test('previous action provider exposes list workflow action schemas', () => {
    const dataProvider = testApp
      .getRegistry()
      .get('builderDataProvider', 'previous_action')

    const previousWorkflowAction = {
      id: 10,
      type: 'csv_file_reader',
      event: 'click',
      element_id: 100,
      order: 1,
      service: {
        id: 20,
        type: 'csv_file_reader',
        schema: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              Email: { title: 'Email', type: 'string' },
            },
          },
        },
      },
    }
    const currentWorkflowAction = {
      id: 11,
      type: 'notification',
      event: 'click',
      element_id: 100,
      order: 2,
    }
    const page = {
      id: 1,
      workflowActions: [previousWorkflowAction, currentWorkflowAction],
    }
    const applicationContext = {
      page,
      element: { id: 100 },
      workflowAction: currentWorkflowAction,
    }

    expect(dataProvider.getDataSchema(applicationContext)).toEqual({
      type: 'object',
      properties: {
        10: {
          title: 'serviceType.coreCSVFileReader ',
          type: 'array',
          items: {
            type: 'object',
            properties: {
              Email: { title: 'Email', type: 'string' },
            },
          },
        },
      },
    })
  })
})
