import { CoreGotoNodeType } from '@baserow/modules/automation/nodeTypes'
import { CoreGotoServiceType } from '@baserow/modules/integrations/core/serviceTypes'
import { TestApp } from '@baserow/test/helpers/testApp'

describe('CoreGotoNodeType', () => {
  test('getType is goto_node', () => {
    expect(CoreGotoNodeType.getType()).toBe('goto')
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

  describe('getHistoryLabel', () => {
    // An app stub whose node registry holds `registeredNodeTypes`, mapping each
    // registered node type to the generic name it falls back to. The enterprise
    // `code` node type is deliberately absent, see the last test.
    const makeApp = ({
      registeredNodeTypes = { local_baserow_get_row: 'Get a single row' },
    } = {}) => ({
      $i18n: {
        t: (key, values) => (values ? `${key}:${JSON.stringify(values)}` : key),
      },
      $registry: {
        exists: (registry, type) => type in registeredNodeTypes,
        // The real registry throws for an unregistered type, so the stub must
        // too, otherwise dropping the `exists` guard would go unnoticed here.
        get: (registry, type) => {
          if (!(type in registeredNodeTypes)) {
            throw new Error(`The type "${type}" is not found.`)
          }
          return { name: registeredNodeTypes[type] }
        },
      },
    })

    test('prefers the destination label resolved by the backend', () => {
      const nodeType = new CoreGotoNodeType({ app: makeApp() })
      expect(
        nodeType.getHistoryLabel({
          nodeHistory: {
            node_label: 'Go to node',
            destination_label: 'Fetch the row',
            destination_node_type: 'local_baserow_get_row',
          },
        })
      ).toBe(
        'nodeType.gotoHistoryLabel:{"label":"Go to node","destination":"Fetch the row"}'
      )
    })

    test('falls back to the destination node type name when it has no label', () => {
      const nodeType = new CoreGotoNodeType({ app: makeApp() })
      expect(
        nodeType.getHistoryLabel({
          nodeHistory: {
            node_label: 'Go to node',
            destination_label: '',
            destination_node_type: 'local_baserow_get_row',
          },
        })
      ).toBe(
        'nodeType.gotoHistoryLabel:{"label":"Go to node","destination":"Get a single row"}'
      )
    })

    test('omits the destination when the jump was skipped', () => {
      // The condition resolved to false, so no jump was followed and the
      // configured destination must not be presented as if it had been.
      const nodeType = new CoreGotoNodeType({ app: makeApp() })
      expect(
        nodeType.getHistoryLabel({
          nodeHistory: {
            node_label: 'Go to node',
            status: 'skipped',
            destination_label: 'Fetch the row',
            destination_node_type: 'local_baserow_get_row',
          },
        })
      ).toBe('Go to node')
    })

    test('omits the destination when none was recorded', () => {
      const nodeType = new CoreGotoNodeType({ app: makeApp() })
      expect(
        nodeType.getHistoryLabel({
          nodeHistory: {
            node_label: 'Go to node',
            destination_label: '',
            destination_node_type: '',
          },
        })
      ).toBe('Go to node')
    })

    test('omits the destination when its node type is not registered', () => {
      // The enterprise `code` node type is only registered when the code runner
      // is configured, so a history entry recorded while it was enabled can
      // outlive its registration and reference a type this build doesn't have.
      const nodeType = new CoreGotoNodeType({ app: makeApp() })
      expect(
        nodeType.getHistoryLabel({
          nodeHistory: {
            node_label: 'Go to node',
            destination_label: '',
            destination_node_type: 'code',
          },
        })
      ).toBe('Go to node')
    })
  })

  describe('getConnections', () => {
    const workflow = { id: 10 }
    const goto = { id: 3, type: 'goto' }

    // An app stub for a linear workflow trigger(1) -> before(2) -> goto(3) ->
    // after(4), where `before` is a valid backward jump and `after` an invalid
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
      // `sibling` shares the goto's level but does not run before it, so it is
      // not a valid jump.
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

    test('returns no connection for a forward jump', () => {
      // `after` runs after the goto node; forward jumps are not allowed.
      const nodeType = new CoreGotoNodeType({
        app: makeApp({ destinationNode: after }),
      })
      const node = { ...goto, service: { destination_service_id: 4 } }
      expect(nodeType.getConnections({ workflow, node })).toEqual([])
    })
  })

  describe('getDestinations', () => {
    const automation = { id: 1 }
    const workflow = { id: 10 }
    const goto = { id: 3, type: 'goto', service: { id: 30 } }

    // A workflow whose graph order (trigger -> second -> first -> goto) differs
    // from its creation order: `second` was inserted above `first`, so it has
    // the higher id while sitting higher up in the editor. Both are valid
    // backward jumps for the goto node.
    const trigger = { id: 1, type: 'trigger', service: { id: 10 } }
    const first = { id: 2, type: 'create_row', service: { id: 20 } }
    const second = { id: 4, type: 'create_row', service: { id: 40 } }
    const inCreationOrder = [trigger, first, goto, second]
    const inGraphOrder = [trigger, second, first, goto]
    const previousByNodeId = {
      [trigger.id]: [],
      [second.id]: [trigger],
      [first.id]: [trigger, second],
      [goto.id]: [trigger, second, first],
    }
    const makeApp = () => ({
      $store: {
        getters: {
          'automationWorkflowNode/getNodes': () => inCreationOrder,
          'automationWorkflowNode/getNodesInOrder': () => inGraphOrder,
          'automationWorkflowNode/getAncestors': () => [],
          'automationWorkflowNode/getPreviousNodes': (_workflow, node) =>
            previousByNodeId[node.id] ?? [],
        },
      },
      $registry: {
        get: (registry, type) => ({
          isTrigger: type === 'trigger',
          getLabel: ({ node }) => `Node ${node.id}`,
        }),
      },
    })

    test('lists the destinations in the order they appear in the editor', () => {
      const nodeType = new CoreGotoNodeType({ app: makeApp() })
      expect(
        nodeType.getDestinations({ workflow, node: goto, automation })
      ).toEqual([
        { value: 40, name: 'Node 4' },
        { value: 20, name: 'Node 2' },
      ])
    })
  })

  describe('afterMove', () => {
    const workflow = { id: 10 }
    const trigger = { id: 1, type: 'trigger' }
    const destination = { id: 2, type: 'create_row', service: { id: 20 } }

    const makeGoto = (destinationServiceId = destination.service.id) => ({
      id: 3,
      type: 'goto',
      service: { condition: {}, destination_service_id: destinationServiceId },
    })

    // An app stub where `previousByNodeId` maps a node id to the nodes the
    // store reports as running before it, so the backward jump check can be
    // exercised.
    const makeApp = (previousByNodeId = {}) => ({
      $store: {
        getters: {
          'automationWorkflowNode/findByServiceId': (_workflow, serviceId) =>
            [trigger, destination].find(
              (node) => node.service?.id === serviceId
            ) || null,
          'automationWorkflowNode/getAncestors': () => [],
          'automationWorkflowNode/getPreviousNodes': (_workflow, node) =>
            previousByNodeId[node.id] ?? [],
        },
      },
      $registry: {
        get: (registry, type) => ({ isTrigger: type === 'trigger' }),
      },
    })

    test('clears a link whose destination left the Go to node path', () => {
      // The destination no longer runs before the Go to node.
      const nodeType = new CoreGotoNodeType({
        app: makeApp({ 2: [trigger], 3: [trigger] }),
      })
      expect(nodeType.afterMove({ workflow, node: makeGoto() })).toEqual({
        service: { condition: {}, destination_service_id: null },
      })
    })

    test('clears a link whose destination is gone from the workflow', () => {
      const nodeType = new CoreGotoNodeType({ app: makeApp() })
      expect(nodeType.afterMove({ workflow, node: makeGoto(999) })).toEqual({
        service: { condition: {}, destination_service_id: null },
      })
    })

    test('keeps a valid backward jump untouched', () => {
      // The destination still runs before the Go to node.
      const nodeType = new CoreGotoNodeType({
        app: makeApp({ 2: [trigger], 3: [trigger, destination] }),
      })
      expect(nodeType.afterMove({ workflow, node: makeGoto() })).toBeNull()
    })

    test('clears a link that became a forward jump', () => {
      // The destination now runs after the Go to node - a forward jump, which
      // is not allowed.
      const nodeType = new CoreGotoNodeType({
        app: makeApp({ 2: [trigger, { id: 3 }], 3: [trigger] }),
      })
      expect(nodeType.afterMove({ workflow, node: makeGoto() })).toEqual({
        service: { condition: {}, destination_service_id: null },
      })
    })

    test('does nothing when no destination is set', () => {
      const nodeType = new CoreGotoNodeType({ app: makeApp() })
      const node = { id: 3, type: 'goto', service: {} }
      expect(nodeType.afterMove({ workflow, node })).toBeNull()
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
      const nodeType = testApp.store.$registry.get('node', 'goto')
      expect(nodeType.constructor.getType()).toBe('goto')
    })

    test('the goto service type is registered', () => {
      const serviceType = testApp.store.$registry.get('service', 'goto')
      expect(serviceType.constructor.getType()).toBe(
        CoreGotoServiceType.getType()
      )
    })
  })
})
