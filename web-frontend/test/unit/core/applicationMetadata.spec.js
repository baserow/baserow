import { expect, test, vi } from 'vitest'
import { createStore } from 'vuex'
import applicationStore from '@baserow/modules/core/store/application'
import { registerApplicationBundle } from '@baserow/modules/core/utils/applicationBundles'
import registerDatabase from '@baserow/modules/database/realtimeMetadata'
import registerAutomation from '@baserow/modules/automation/realtimeMetadata'

test.each([
  ['database', 'tables', 'table', 'database_id', registerDatabase],
  [
    'automation',
    'workflows',
    'automation_workflow',
    'automation_id',
    registerAutomation,
  ],
])(
  'keeps unopened %s child lists current without initializing the application',
  async (type, children, event, parentKey, register) => {
    const store = createStore({ modules: { application: applicationStore } })
    store.commit('application/SET_ITEMS', [{ id: 1, type, [children]: [] }])
    const callbacks = new Map()
    const app = {
      $store: store,
      $realtime: {
        registerEvent: (name, callback) => callbacks.set(name, callback),
      },
    }
    const initialize = vi.fn(async () => ({}))
    registerApplicationBundle(app, type, initialize)
    register(app)
    const dataKey = type === 'database' ? 'table' : 'workflow'
    const emit = async (suffix, data) =>
      callbacks.get(`${event}_${suffix}`)({}, data)

    await emit('created', {
      [dataKey]: { id: 2, [parentKey]: 1, name: 'New child' },
    })
    await emit('updated', {
      [dataKey]: { id: 2, [parentKey]: 1, name: 'Renamed child' },
    })
    expect(
      store.getters['application/get'](1)[children].map((child) => child.name)
    ).toEqual(['Renamed child'])
    await emit('deleted', { [parentKey]: 1, [`${dataKey}_id`]: 2 })
    expect(store.getters['application/get'](1)[children]).toEqual([])
    expect(initialize).not.toHaveBeenCalled()
    expect(store.hasModule('field')).toBe(false)
    expect(store.hasModule('automationWorkflow')).toBe(false)
  }
)
