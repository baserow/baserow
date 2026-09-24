import { Event } from '@baserow/modules/builder/eventTypes'

describe('Builder event types', () => {
  test('handles a workflow action whose data source no longer exists', async () => {
    const page = { id: 1, elements: [] }
    const sharedPage = { id: 2, elements: [] }
    const workflowAction = {
      id: 3,
      type: 'refresh_data_source',
      data_source_id: 4,
    }
    const workflowActionType = {
      label: 'Refresh data source',
      execute: vi.fn(({ applicationContext }) => {
        return applicationContext.workflowActionContext.dataSourcePage.elements
      }),
    }
    const app = {
      $i18n: { t: (key) => key },
      $registry: {
        get: vi.fn((registryName) => {
          if (registryName === 'element') {
            return { uniqueElementId: () => 'element-5' }
          }
          return workflowActionType
        }),
        getAll: vi.fn(() => []),
      },
      $store: {
        dispatch: vi.fn(),
        getters: {
          'page/getSharedPage': () => sharedPage,
          'dataSource/getPagesDataSourceById': () => undefined,
        },
      },
    }
    const event = new Event({ app, name: 'submit', label: 'Submit' })

    await expect(
      event.fire({
        workflowActions: [workflowAction],
        applicationContext: {
          builder: { id: 6 },
          element: { id: 5, type: 'form_container' },
          page,
        },
      })
    ).resolves.toBeUndefined()

    expect(app.$store.dispatch).toHaveBeenCalledWith(
      'builderToast/error',
      expect.objectContaining({
        message:
          'builderToast.errorWorkflowActionDispatchbuilderToast.defaultMessage',
      })
    )
    expect(app.$store.dispatch).toHaveBeenLastCalledWith(
      'builderWorkflowAction/setDispatching',
      {
        workflowAction,
        dispatchedById: null,
        isDispatching: false,
      }
    )
  })
})
