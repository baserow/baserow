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

  test('delete resolves a form distinct from create and update', () => {
    const registry = testApp._app.$registry
    const create = registry.get('databaseWorkflowActionType', 'create_row')
    const update = registry.get('databaseWorkflowActionType', 'update_row')
    const del = registry.get('databaseWorkflowActionType', 'delete_row')

    // Update's form wraps create's upsert form (LocalBaserowUpdateRowServiceForm
    // renders LocalBaserowUpsertRowServiceForm), so they are related but not the
    // same component instance. Delete must not resolve to either of them.
    expect(del.serviceType.formComponent).not.toBe(
      create.serviceType.formComponent
    )
    expect(del.serviceType.formComponent).not.toBe(
      update.serviceType.formComponent
    )
  })
})
