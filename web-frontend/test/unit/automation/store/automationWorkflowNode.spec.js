import { TestApp } from '@baserow/test/helpers/testApp'
import nodeStore, {
  getWorkflowImmediateDispatch,
} from '@baserow/modules/automation/store/automationWorkflowNode'

describe('Automation workflow node store', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  test.each([
    ['manual', true],
    ['periodic', true],
    ['http_trigger', false],
    ['local_baserow_rows_created', false],
  ])('computes immediate dispatch for %s triggers', (type, expected) => {
    const workflow = {
      nodes: [
        {
          id: 1,
          type,
          service: {},
        },
      ],
    }

    expect(getWorkflowImmediateDispatch(testApp.getRegistry(), workflow)).toBe(
      expected
    )
  })

  test('updates workflow immediate dispatch after replacing the trigger', async () => {
    const trigger = {
      id: 1,
      type: 'local_baserow_rows_created',
      service: {},
    }
    const workflow = {
      id: 2,
      graph: { 0: trigger.id },
      immediate_dispatch: false,
      nodes: [trigger],
      nodeMap: {
        [trigger.id]: trigger,
      },
    }

    testApp.mock.onPost(`automation/node/${trigger.id}/replace/`).reply(200, {
      id: 3,
      type: 'manual',
      service: {},
      workflow: workflow.id,
    })

    await testApp.store.dispatch('automationWorkflowNode/replace', {
      workflow,
      nodeId: trigger.id,
      newType: 'manual',
    })

    expect(workflow.immediate_dispatch).toBe(true)
  })

  test('optimistically updates workflow immediate dispatch while replacing the trigger', async () => {
    const trigger = {
      id: 1,
      type: 'local_baserow_rows_created',
      service: {},
    }
    const workflow = {
      id: 2,
      graph: { 0: trigger.id },
      immediate_dispatch: false,
      nodes: [trigger],
      nodeMap: {
        [trigger.id]: trigger,
      },
    }

    let resolveRequest
    let requestStarted
    const requestStartedPromise = new Promise((resolve) => {
      requestStarted = resolve
    })
    const responsePromise = new Promise((resolve) => {
      resolveRequest = () =>
        resolve([
          200,
          {
            id: 3,
            type: 'manual',
            service: {},
            workflow: workflow.id,
          },
        ])
    })

    testApp.mock.onPost(`automation/node/${trigger.id}/replace/`).reply(() => {
      requestStarted()
      return responsePromise
    })

    const replacePromise = testApp.store.dispatch(
      'automationWorkflowNode/replace',
      {
        workflow,
        nodeId: trigger.id,
        newType: 'manual',
      }
    )

    await requestStartedPromise

    expect(workflow.immediate_dispatch).toBe(true)

    resolveRequest()
    await replacePromise
  })

  test('optimistically updates workflow immediate dispatch while creating a trigger', async () => {
    const workflow = {
      id: 2,
      graph: {},
      immediate_dispatch: false,
      nodes: [],
      nodeMap: {},
      automation_id: 3,
    }

    let resolveRequest
    let requestStarted
    const requestStartedPromise = new Promise((resolve) => {
      requestStarted = resolve
    })
    const responsePromise = new Promise((resolve) => {
      resolveRequest = () =>
        resolve([
          200,
          {
            id: 1,
            type: 'manual',
            service: {},
            workflow: workflow.id,
          },
        ])
    })

    testApp.mock
      .onPost(`automation/workflow/${workflow.id}/nodes/`)
      .reply(() => {
        requestStarted()
        return responsePromise
      })
    testApp.mock
      .onGet(`applications/${workflow.automation_id}/permissions/`)
      .reply(200, {})

    const createPromise = testApp.store.dispatch(
      'automationWorkflowNode/create',
      {
        workflow,
        type: 'manual',
        referenceNode: null,
        position: 'south',
        output: '',
      }
    )

    await requestStartedPromise

    expect(workflow.immediate_dispatch).toBe(true)

    resolveRequest()
    await createPromise
  })

  describe('getNodesInOrder', () => {
    // A workflow whose graph order (1 -> 4 -> 2 -> 3) differs from its creation
    // order, which is what `workflow.nodes` holds: node 4 was inserted between
    // the trigger and node 2, so its id is the highest while it sits second.
    const makeWorkflow = () => {
      const nodes = [
        { id: 1, type: 'manual' },
        { id: 2, type: 'create_row' },
        { id: 3, type: 'goto' },
        { id: 4, type: 'create_row' },
      ]
      return {
        id: 10,
        nodes,
        nodeMap: Object.fromEntries(nodes.map((node) => [`${node.id}`, node])),
        graph: {
          0: 1,
          1: { next: { '': [4] } },
          4: { next: { '': [2] } },
          2: { next: { '': [3] } },
          3: {},
        },
      }
    }

    const idsOf = (nodes) => nodes.map((node) => node.id)

    test('returns the nodes in the order they appear in the editor', () => {
      const workflow = makeWorkflow()
      // `getNodes` returns creation order, which no longer matches the graph.
      expect(
        idsOf(
          testApp.store.getters['automationWorkflowNode/getNodes'](workflow)
        )
      ).toEqual([1, 2, 3, 4])
      expect(
        idsOf(
          testApp.store.getters['automationWorkflowNode/getNodesInOrder'](
            workflow
          )
        )
      ).toEqual([1, 4, 2, 3])
    })

    test('includes nodes on non-default router branches', () => {
      // Router node 2 has a named branch (create_row 3 -> goto 4) and a
      // default branch (create_row 5 -> goto 6). The named branch's nodes were
      // previously missing from the order, which hid them from the "Go to
      // node" destination dropdown.
      const nodes = [
        { id: 1, type: 'manual' },
        { id: 2, type: 'router' },
        { id: 3, type: 'create_row' },
        { id: 4, type: 'goto' },
        { id: 5, type: 'create_row' },
        { id: 6, type: 'goto' },
      ]
      const workflow = {
        id: 10,
        nodes,
        nodeMap: Object.fromEntries(nodes.map((node) => [`${node.id}`, node])),
        graph: {
          0: 1,
          1: { next: { '': [2] } },
          2: { next: { 'branch-uuid': [3], '': [5] } },
          3: { next: { '': [4] } },
          4: {},
          5: { next: { '': [6] } },
          6: {},
        },
      }
      expect(
        idsOf(
          testApp.store.getters['automationWorkflowNode/getNodesInOrder'](
            workflow
          )
        )
      ).toEqual([1, 2, 3, 4, 5, 6])
    })

    test('returns nothing without a workflow', () => {
      expect(
        testApp.store.getters['automationWorkflowNode/getNodesInOrder'](null)
      ).toEqual([])
    })
  })

  describe('realtime form-reset metadata', () => {
    const makeWorkflow = () => {
      const node = {
        id: 10,
        type: 'manual',
        service: { foo: 'a' },
        _: { loading: false, viaRealtime: false, realtimeVersion: 0 },
      }
      const workflow = { id: 1, nodes: [node], nodeMap: { 10: node } }
      return { workflow, node }
    }

    test('a realtime (override) update replaces the node, flags it and bumps the version', () => {
      const { workflow } = makeWorkflow()

      nodeStore.mutations.UPDATE_ITEM(
        {},
        {
          workflow,
          node: { id: 10 },
          values: { id: 10, type: 'manual', service: { foo: 'b' } },
          override: true,
          viaRealtime: true,
        }
      )

      const updated = workflow.nodeMap[10]
      expect(updated.service.foo).toBe('b')
      expect(updated._.viaRealtime).toBe(true)
      // Version carried across the object replacement, then bumped once.
      expect(updated._.realtimeVersion).toBe(1)
    })

    test('a local (merge) update clears the flag without bumping the version', () => {
      const { workflow, node } = makeWorkflow()
      node._.viaRealtime = true
      node._.realtimeVersion = 3

      nodeStore.mutations.UPDATE_ITEM(
        {},
        { workflow, node: { id: 10 }, values: { service: { foo: 'c' } } }
      )

      expect(node._.viaRealtime).toBe(false)
      expect(node._.realtimeVersion).toBe(3)
    })
  })
})
