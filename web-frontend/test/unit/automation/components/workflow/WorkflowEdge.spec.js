import { ref } from 'vue'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import WorkflowEdge from '@baserow/modules/automation/components/workflow/WorkflowEdge'

// WorkflowEdge reads its drop/add context from the automationWorkflowNode store
// getters. We mock the vuex store so we can drive nextNodesOnEdge precisely.
const storeHolder = vi.hoisted(() => ({ store: null }))
// Override only useStore; keep the real vuex exports. Replacing the whole module
// would strip mapGetters/mapActions/etc., and since the mock applies for the
// entire worker, any sibling module loaded alongside this spec (e.g. enterprise
// components pulled in during the Nuxt test-app bootstrap) would crash with
// "No mapGetters export is defined on the vuex mock".
vi.mock('vuex', async (importOriginal) => ({
  ...(await importOriginal()),
  useStore: () => storeHolder.store,
}))

const node = (id) => ({ id })

const setStore = ({
  draggingNodeId = null,
  nodesById = {},
  children = [],
  nextNodes = [],
  ancestors = [],
} = {}) => {
  storeHolder.store = {
    getters: {
      'automationWorkflowNode/getDraggingNodeId': draggingNodeId,
      'automationWorkflowNode/findById': (workflow, id) =>
        nodesById[id] ?? null,
      'automationWorkflowNode/getChildren': () => children,
      'automationWorkflowNode/getNextNodes': () => nextNodes,
      'automationWorkflowNode/getAncestors': () => ancestors,
    },
  }
}

const mountEdge = (props) =>
  mountSuspended(WorkflowEdge, {
    props,
    global: {
      provide: { workflow: ref({ id: 1 }) },
      stubs: {
        WorkflowNode: true,
        WorkflowAddBtnNode: {
          name: 'WorkflowAddBtnNode',
          template:
            '<button class="add-btn" @click="$emit(\'add-node\', \'action\')" />',
        },
      },
    },
  })

describe('WorkflowEdge head-of-edge insertion', () => {
  afterEach(() => {
    storeHolder.store = null
  })

  describe('container child slot with an existing first child', () => {
    // The reported bug: dropping/adding above the first child (a router) must
    // insert BEFORE it via 'north', not append onto the router's default edge.
    const props = { node: node(16), isChild: true, edgeUid: '' }

    test('drop emits a north move referencing the first child', async () => {
      setStore({
        draggingNodeId: 18,
        nodesById: { 18: node(18) },
        children: [node(17)],
      })
      const wrapper = await mountEdge(props)

      await wrapper.find('.workflow-edge__dropzone').trigger('drop')

      expect(wrapper.emitted('move-node')[0][0]).toEqual({
        referenceNodeId: 17,
        position: 'north',
        output: '',
      })
    })

    test('add emits a north create referencing the first child', async () => {
      setStore({ children: [node(17)] })
      const wrapper = await mountEdge(props)

      await wrapper.find('.add-btn').trigger('click')

      expect(wrapper.emitted('add-node')[0][0]).toEqual({
        type: 'action',
        referenceNode: node(17),
        position: 'north',
        output: '',
      })
    })
  })

  describe('empty container child slot', () => {
    const props = { node: node(16), isChild: true, edgeUid: '' }

    test('drop emits a child move referencing the container', async () => {
      setStore({
        draggingNodeId: 18,
        nodesById: { 18: node(18) },
        children: [],
      })
      const wrapper = await mountEdge(props)

      await wrapper.find('.workflow-edge__dropzone').trigger('drop')

      expect(wrapper.emitted('move-node')[0][0]).toEqual({
        referenceNodeId: 16,
        position: 'child',
        output: '',
      })
    })

    test('add emits a child create referencing the container', async () => {
      setStore({ children: [] })
      const wrapper = await mountEdge(props)

      await wrapper.find('.add-btn').trigger('click')

      expect(wrapper.emitted('add-node')[0][0]).toEqual({
        type: 'action',
        referenceNode: node(16),
        position: 'child',
        output: '',
      })
    })
  })

  describe('next edge with an existing node', () => {
    const props = { node: node(17), isChild: false, edgeUid: 'branch-uuid' }

    test('drop emits a north move referencing the first node on the edge', async () => {
      setStore({
        draggingNodeId: 99,
        nodesById: { 99: node(99) },
        nextNodes: [node(18)],
      })
      const wrapper = await mountEdge(props)

      await wrapper.find('.workflow-edge__dropzone').trigger('drop')

      expect(wrapper.emitted('move-node')[0][0]).toEqual({
        referenceNodeId: 18,
        position: 'north',
        output: '',
      })
    })
  })

  describe('empty next edge', () => {
    const props = { node: node(17), isChild: false, edgeUid: '' }

    test('drop emits a south move on the edge', async () => {
      setStore({
        draggingNodeId: 99,
        nodesById: { 99: node(99) },
        nextNodes: [],
      })
      const wrapper = await mountEdge(props)

      await wrapper.find('.workflow-edge__dropzone').trigger('drop')

      expect(wrapper.emitted('move-node')[0][0]).toEqual({
        referenceNodeId: 17,
        position: 'south',
        output: '',
      })
    })
  })
})
