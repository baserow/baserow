import nodeStore from '@baserow/modules/automation/store/automationWorkflowNode'

const afterMove = nodeStore.actions.afterMove

describe('afterMove', () => {
  const workflow = { id: 1 }
  const trigger = { id: 1, type: 'trigger' }
  const action = { id: 2, type: 'create_row' }
  const goto = { id: 3, type: 'goto' }

  /**
   * Runs the action against a mocked Vuex context, where a node type's
   * `afterMove` returns the values keyed by its type in `valuesByType`, and
   * null for every other type.
   */
  function run(nodes, valuesByType) {
    const dispatched = []
    const dispatch = (name, payload) => dispatched.push({ name, payload })
    const getters = { getNodes: () => nodes }
    const thisArg = {
      $registry: {
        get: (kind, type) => ({
          afterMove: () => valuesByType[type] ?? null,
        }),
      },
    }
    afterMove.call(thisArg, { dispatch, getters }, { workflow })
    return dispatched
  }

  test('updates only the nodes their type asks to reconcile', () => {
    const values = { service: { destination_service_id: null } }
    const dispatched = run([trigger, action, goto], { goto: values })
    expect(dispatched).toEqual([
      { name: 'forceUpdate', payload: { workflow, node: goto, values } },
    ])
  })

  test('leaves every node untouched when no type reconciles', () => {
    expect(run([trigger, action, goto], {})).toHaveLength(0)
  })
})
