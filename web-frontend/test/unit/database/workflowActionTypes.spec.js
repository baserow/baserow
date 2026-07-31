import { TestApp } from '@baserow/test/helpers/testApp'

describe('databaseWorkflowActionType registry', () => {
  let testApp = null

  beforeAll(() => {
    testApp = new TestApp()
  })

  afterEach(() => {
    testApp.afterEach()
  })

  test('the three types are registered', () => {
    const types = testApp._app.$registry.getAll('databaseWorkflowActionType')
    expect(Object.keys(types).sort()).toEqual([
      'create_row',
      'delete_row',
      'update_row',
    ])
  })

  test('each type resolves a service type with a form component', () => {
    const registry = testApp._app.$registry
    for (const type of ['create_row', 'update_row', 'delete_row']) {
      const actionType = registry.get('databaseWorkflowActionType', type)
      expect(actionType.serviceType).toBeTruthy()
      expect(actionType.serviceType.formComponent).toBeTruthy()
      expect(actionType.label).toBeTruthy()
      expect(actionType.icon).toBeTruthy()
    }
  })

  test('each type resolves the exact service type it declares', () => {
    const registry = testApp._app.$registry
    const cases = [
      ['create_row', 'local_baserow_create_row'],
      ['update_row', 'local_baserow_update_row'],
      ['delete_row', 'local_baserow_delete_row'],
    ]
    for (const [actionType, serviceType] of cases) {
      expect(
        registry.get('databaseWorkflowActionType', actionType).serviceType
      ).toBe(registry.get('service', serviceType))
    }
  })
})
