import { CoreGotoNodeType } from '@baserow/modules/automation/nodeTypes'
import { CoreGotoServiceType } from '@baserow/modules/integrations/core/serviceTypes'
import { TestApp } from '@baserow/test/helpers/testApp'

describe('CoreGotoNodeType', () => {
  test('getType is goto_node', () => {
    expect(CoreGotoNodeType.getType()).toBe('goto_node')
  })

  test('name comes from the i18n label', () => {
    const nodeType = new CoreGotoNodeType({
      app: { $i18n: { t: (key) => key } },
    })
    expect(nodeType.name).toBe('nodeType.gotoNodeLabel')
  })

  describe('getDefaultLabel', () => {
    const automation = { id: 1 }

    // An app stub where the destination node resolves to a node type whose
    // label is `destinationLabel`, and i18n interpolates the destination.
    const makeApp = ({
      destinationNode = null,
      destinationLabel = '',
    } = {}) => ({
      $i18n: {
        t: (key, values) => (values ? `${key}:${JSON.stringify(values)}` : key),
      },
      $store: {
        getters: {
          'automationWorkflow/getById': () => ({ id: 10 }),
          'automationWorkflowNode/findByServiceId': () => destinationNode,
        },
      },
      $registry: {
        get: () => ({
          getLabel: () => destinationLabel,
        }),
      },
    })

    test('falls back to the name when there is no destination', () => {
      const nodeType = new CoreGotoNodeType({ app: makeApp() })
      const node = { workflow: 10, service: {} }
      expect(nodeType.getDefaultLabel({ automation, node })).toBe(
        'nodeType.gotoNodeLabel'
      )
    })

    test('falls back to the name when the destination cannot be resolved', () => {
      const nodeType = new CoreGotoNodeType({
        app: makeApp({ destinationNode: null }),
      })
      const node = { workflow: 10, service: { destination_service_id: 5 } }
      expect(nodeType.getDefaultLabel({ automation, node })).toBe(
        'nodeType.gotoNodeLabel'
      )
    })

    test('appends the destination node label once a destination is set', () => {
      const nodeType = new CoreGotoNodeType({
        app: makeApp({
          destinationNode: { id: 5, type: 'create_row' },
          destinationLabel: 'List rows',
        }),
      })
      const node = { workflow: 10, service: { destination_service_id: 5 } }
      expect(nodeType.getDefaultLabel({ automation, node })).toBe(
        'nodeType.gotoNodeLabelWithDestination:{"destination":"List rows"}'
      )
    })
  })

  describe('getConnections', () => {
    const workflow = { id: 10 }
    const goto = { id: 3, type: 'goto_node' }

    // An app stub for a linear workflow trigger(1) -> before(2) -> goto(3) ->
    // after(4), where `before` is a valid backward jump and `after` a valid
    // forward jump. `sibling` sits at the same level but off the goto's path.
    const trigger = { id: 1, type: 'trigger' }
    const before = { id: 2, type: 'create_row' }
    const after = { id: 4, type: 'create_row' }
    const sibling = { id: 5, type: 'create_row' }
    const previousByNodeId = {
      [trigger.id]: [],
      [before.id]: [trigger],
      [goto.id]: [trigger, before],
      [after.id]: [trigger, before, goto],
      [sibling.id]: [],
    }
    const makeApp = ({ destinationNode = before } = {}) => ({
      $store: {
        getters: {
          'automationWorkflowNode/findByServiceId': () => destinationNode,
          'automationWorkflowNode/getAncestors': () => [],
          'automationWorkflowNode/getPreviousNodes': (workflow, node) =>
            previousByNodeId[node.id] ?? [],
        },
      },
      $registry: {
        get: (registry, type) => ({ isTrigger: type === 'trigger' }),
      },
    })

    test('returns no connection when there is no destination', () => {
      const nodeType = new CoreGotoNodeType({ app: makeApp() })
      const node = { ...goto, service: {} }
      expect(nodeType.getConnections({ workflow, node })).toEqual([])
    })

    test('returns no connection when the destination cannot be resolved', () => {
      const nodeType = new CoreGotoNodeType({
        app: makeApp({ destinationNode: null }),
      })
      const node = { ...goto, service: { destination_service_id: 2 } }
      expect(nodeType.getConnections({ workflow, node })).toEqual([])
    })

    test('returns no connection when the jump is invalid', () => {
      // `sibling` shares the goto's level but is on neither its backward nor its
      // forward path, so it is not a valid jump.
      const nodeType = new CoreGotoNodeType({
        app: makeApp({ destinationNode: sibling }),
      })
      const node = { ...goto, service: { destination_service_id: 5 } }
      expect(nodeType.getConnections({ workflow, node })).toEqual([])
    })

    test('returns the destination connection for a backward jump', () => {
      const nodeType = new CoreGotoNodeType({ app: makeApp() })
      const node = { ...goto, service: { destination_service_id: 2 } }
      expect(nodeType.getConnections({ workflow, node })).toEqual([
        { destinationNodeId: 2 },
      ])
    })

    test('returns the destination connection for a forward jump', () => {
      const nodeType = new CoreGotoNodeType({
        app: makeApp({ destinationNode: after }),
      })
      const node = { ...goto, service: { destination_service_id: 4 } }
      expect(nodeType.getConnections({ workflow, node })).toEqual([
        { destinationNodeId: 4 },
      ])
    })
  })

  describe('registration', () => {
    let testApp = null

    beforeEach(() => {
      testApp = new TestApp()
    })

    afterEach(() => {
      testApp.afterEach()
    })

    test('the goto node type is registered', () => {
      const nodeType = testApp.store.$registry.get('node', 'goto_node')
      expect(nodeType.constructor.getType()).toBe('goto_node')
    })

    test('the goto service type is registered', () => {
      const serviceType = testApp.store.$registry.get('service', 'goto')
      expect(serviceType.constructor.getType()).toBe(
        CoreGotoServiceType.getType()
      )
    })
  })
})
