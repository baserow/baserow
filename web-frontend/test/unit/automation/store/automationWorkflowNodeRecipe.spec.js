import { TestApp } from '@baserow/test/helpers/testApp'
import { UNDO_REDO_ACTION_GROUP_HEADER } from '@baserow/modules/database/utils/action'

describe('automationWorkflowNode createFromRecipe', () => {
  let testApp = null
  let store = null
  let workflow = null
  let trigger = null
  // Nodes as the server stores them, keyed by id, so PATCH replies can echo
  // the merged node back the way the real backend does.
  let serverNodes = null
  let nextId = null
  let createCount = null
  // When set, the n-th create request fails with a validation error.
  let failCreateNumber = null
  // When set, the update of that node fails as if the connection dropped.
  let failUpdateNodeId = null
  // Ids of the nodes whose delete fails as if the connection dropped.
  let failDeleteNodeIds = null
  // A reply that throws reaches the client as a request without a response,
  // the way a dropped connection does.
  const connectionDropped = () => {
    throw new Error('Network Error')
  }
  const nodeIdOf = (config) =>
    Number(config.url.match(/automation\/node\/(\d+)\/$/)[1])

  const groupIdOf = (request) => request.headers[UNDO_REDO_ACTION_GROUP_HEADER]
  const recipe = (type) =>
    testApp.getRegistry().get('automationNodeRecipe', type)
  const nodeIds = () =>
    store.getters['automationWorkflowNode/getNodes'](workflow).map(
      (node) => node.id
    )
  const orderedIds = () =>
    store.getters['automationWorkflowNode/getNodesInOrder'](workflow).map(
      (node) => node.id
    )
  const findById = (id) =>
    store.getters['automationWorkflowNode/findById'](workflow, id)
  const selectedId = () =>
    store.getters['automationWorkflowNode/getSelected'](workflow)?.id ?? null
  const fromRecipe = (type) =>
    store.dispatch('automationWorkflowNode/createFromRecipe', {
      workflow,
      recipe: recipe(type),
      referenceNode: trigger,
      position: 'south',
      output: '',
    })

  beforeEach(() => {
    testApp = new TestApp()
    store = testApp.store
    trigger = { id: 1, type: 'manual', workflow: 7, service: { id: 11 } }
    workflow = {
      id: 7,
      automation_id: 3,
      nodes: [],
      nodeMap: {},
      graph: { 0: 1, 1: {} },
      selectedNodeId: null,
      immediate_dispatch: true,
    }
    store.commit('automationWorkflowNode/SET_ITEMS', {
      workflow,
      nodes: [trigger],
    })
    serverNodes = {}
    nextId = 2
    createCount = 0
    failCreateNumber = null
    failUpdateNodeId = null
    failDeleteNodeIds = []

    testApp.mock
      .onPost(`automation/workflow/${workflow.id}/nodes/`)
      .reply((config) => {
        createCount += 1
        if (createCount === failCreateNumber) {
          return [400, { error: 'ERROR_REQUEST_BODY_VALIDATION' }]
        }
        const { type } = JSON.parse(config.data)
        const id = nextId++
        serverNodes[id] = {
          id,
          type,
          workflow: workflow.id,
          label: '',
          service: { id: id * 10 },
        }
        return [200, serverNodes[id]]
      })
    testApp.mock.onPatch(/automation\/node\/\d+\/$/).reply((config) => {
      const id = nodeIdOf(config)
      if (id === failUpdateNodeId) {
        connectionDropped()
      }
      const values = JSON.parse(config.data)
      const node = serverNodes[id]
      serverNodes[id] = {
        ...node,
        ...values,
        service: { ...node.service, ...(values.service || {}) },
      }
      return [200, serverNodes[id]]
    })
    testApp.mock.onDelete(/automation\/node\/\d+\/$/).reply((config) => {
      if (failDeleteNodeIds.includes(nodeIdOf(config))) {
        connectionDropped()
      }
      return [204]
    })
    testApp.mock
      .onGet(`applications/${workflow.automation_id}/permissions/`)
      .reply(200, {})
    // The first node is selected through a timer once the whole recipe is in.
    vi.useFakeTimers()
  })

  afterEach(async () => {
    vi.useRealTimers()
    await testApp.afterEach()
  })

  test('inserts the While loop nodes in order under one undo action group', async () => {
    const created = await fromRecipe('while_loop')

    expect(created.map((node) => node.id)).toEqual([2, 3])
    expect(orderedIds()).toEqual([1, 2, 3])

    const { post, patch } = testApp.mock.history
    expect(post.map((request) => JSON.parse(request.data))).toEqual([
      {
        type: 'local_baserow_list_rows',
        reference_node_id: 1,
        position: 'south',
        output: '',
      },
      { type: 'goto', reference_node_id: 2, position: 'south', output: '' },
    ])
    expect(patch.map((request) => request.url)).toEqual([
      expect.stringMatching(/automation\/node\/2\/$/),
      expect.stringMatching(/automation\/node\/3\/$/),
    ])
    expect(patch.map((request) => JSON.parse(request.data))).toEqual([
      { label: 'nodeRecipe.whileLoopListRowsLabel' },
      {
        label: 'nodeRecipe.whileLoopGotoLabel',
        service: {
          destination_service_id: 20,
          condition: {
            formula: "greater_than(length(get('previous_node.2')), 0)",
            mode: 'advanced',
          },
        },
      },
    ])

    // One undo takes the whole recipe back: every request shares the group.
    const groupIds = new Set([...post, ...patch].map(groupIdOf))
    expect(groupIds.size).toBe(1)
    expect([...groupIds][0]).toEqual(expect.any(String))

    const listRows = findById(2)
    const goto = findById(3)
    expect(listRows.label).toBe('nodeRecipe.whileLoopListRowsLabel')
    expect(listRows.service).toEqual({ id: 20 })
    expect(goto.label).toBe('nodeRecipe.whileLoopGotoLabel')
    expect(goto.service.destination_service_id).toBe(listRows.service.id)
  })

  test('inserts the For loop Iterator with its label and range(5) source', async () => {
    await fromRecipe('for_loop')

    expect(orderedIds()).toEqual([1, 2])

    const { post, patch } = testApp.mock.history
    expect(post).toHaveLength(1)
    expect(JSON.parse(post[0].data)).toEqual({
      type: 'iterator',
      reference_node_id: 1,
      position: 'south',
      output: '',
    })
    expect(patch).toHaveLength(1)
    expect(JSON.parse(patch[0].data)).toEqual({
      label: 'nodeRecipe.forLoopIteratorLabel',
      service: { source: { formula: 'range(5)', mode: 'advanced' } },
    })
    expect(groupIdOf(patch[0])).toBe(groupIdOf(post[0]))

    const iterator = findById(2)
    expect(iterator.label).toBe('nodeRecipe.forLoopIteratorLabel')
    expect(iterator.service.source).toEqual({
      formula: 'range(5)',
      mode: 'advanced',
    })
  })

  test('selects the first node only once the whole recipe is in', async () => {
    await fromRecipe('while_loop')

    expect(selectedId()).toBeNull()

    vi.runAllTimers()

    expect(selectedId()).toBe(2)
  })

  test('removes the nodes created so far and rethrows when a later step fails', async () => {
    testApp.dontFailOnErrorResponses()
    // The Go to node's create is the second request.
    failCreateNumber = 2

    await expect(fromRecipe('while_loop')).rejects.toThrow()

    expect(nodeIds()).toEqual([1])
    expect(orderedIds()).toEqual([1])

    const { post, patch, delete: deletes } = testApp.mock.history
    expect(post).toHaveLength(2)
    expect(patch).toHaveLength(1)
    expect(deletes.map((request) => request.url)).toEqual([
      expect.stringMatching(/automation\/node\/2\/$/),
    ])
    // The rollback shares the failed attempt's group, so undoing it is a
    // no-op instead of resurrecting the half-inserted recipe.
    expect(new Set([...post, ...patch, ...deletes].map(groupIdOf)).size).toBe(1)

    vi.runAllTimers()

    expect(selectedId()).toBeNull()
  })

  test('keeps the node it cannot remove and warns when the connection drops', async () => {
    testApp.dontFailOnErrorResponses()
    // The List rows node is created, then the connection drops: its update
    // fails and so does the delete that should take it back out.
    failUpdateNodeId = 2
    failDeleteNodeIds = [2]

    await expect(fromRecipe('while_loop')).rejects.toThrow()

    // The node is still on the server, so it stays in the editor too.
    expect(orderedIds()).toEqual([1, 2])

    const { post, patch, delete: deletes } = testApp.mock.history
    expect(post).toHaveLength(1)
    expect(patch).toHaveLength(1)
    expect(deletes).toHaveLength(1)

    expect(store.state.toast.items).toEqual([
      expect.objectContaining({
        type: 'warning',
        title: 'nodeRecipe.nodesLeftTitle',
        message: 'nodeRecipe.nodesLeftMessage',
      }),
    ])

    vi.runAllTimers()

    expect(selectedId()).toBeNull()
  })

  test('stops the rollback at the first node it cannot remove', async () => {
    testApp.dontFailOnErrorResponses()
    // Both nodes are created; the Go to node's update fails, then its delete.
    failUpdateNodeId = 3
    failDeleteNodeIds = [3]

    await expect(fromRecipe('while_loop')).rejects.toThrow()

    // The List rows node is not touched: what stays is the start of the
    // recipe, not a Go to node without the List rows it jumps back to.
    expect(orderedIds()).toEqual([1, 2, 3])
    const { delete: deletes } = testApp.mock.history
    expect(deletes.map((request) => request.url)).toEqual([
      expect.stringMatching(/automation\/node\/3\/$/),
    ])
    expect(store.state.toast.items).toHaveLength(1)
  })

  test('a plain create still selects the node and carries no undo group', async () => {
    await store.dispatch('automationWorkflowNode/create', {
      workflow,
      type: 'iterator',
      referenceNode: trigger,
      position: 'south',
      output: '',
    })

    expect(groupIdOf(testApp.mock.history.post[0])).toBeUndefined()

    vi.runAllTimers()

    expect(selectedId()).toBe(2)
  })

  test('a create can leave the node unselected', async () => {
    await store.dispatch('automationWorkflowNode/create', {
      workflow,
      type: 'iterator',
      referenceNode: trigger,
      position: 'south',
      output: '',
      select: false,
    })

    vi.runAllTimers()

    expect(orderedIds()).toEqual([1, 2])
    expect(selectedId()).toBeNull()
  })
})
