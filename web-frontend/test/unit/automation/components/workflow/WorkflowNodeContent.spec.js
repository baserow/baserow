import { ref } from 'vue'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import WorkflowNodeContent from '@baserow/modules/automation/components/workflow/WorkflowNodeContent'
import MarkdownContext from '@baserow/modules/core/components/MarkdownContext'

vi.mock('@vue-flow/core', () => ({
  useVueFlow: () => ({ onMove: () => {} }),
}))

const mountNode = (node, props = {}) => {
  const workflow = { id: 1, graph: { 0: node.id, [node.id]: {} } }
  return mountSuspended(WorkflowNodeContent, {
    props: { node, ...props },
    global: {
      provide: {
        workflow: ref(workflow),
        automation: ref({ id: 2, integrations: [] }),
        workspace: ref({ id: 3 }),
      },
      stubs: { WorkflowNodeContext: true },
    },
  })
}

const buildNode = (values = {}) => ({
  id: 10,
  type: 'local_baserow_rows_created',
  label: 'New order',
  note: '',
  workflow: 1,
  service: { id: 20, type: 'local_baserow_rows_created' },
  _: { loading: false },
  ...values,
})

describe('WorkflowNodeContent note', () => {
  test('a node without a note has no note icon', async () => {
    const wrapper = await mountNode(buildNode())

    expect(wrapper.find('.workflow-node-content__note').exists()).toBe(false)
    expect(wrapper.findComponent(MarkdownContext).exists()).toBe(false)
  })

  test('a node with a note shows the icon and passes the note on', async () => {
    const wrapper = await mountNode(buildNode({ note: 'Why **this** step' }))

    expect(wrapper.find('.workflow-node-content__note').exists()).toBe(true)
    expect(wrapper.findComponent(MarkdownContext).props('content')).toBe(
      'Why **this** step'
    )
  })

  test('the note icon is shown on a read-only node', async () => {
    const wrapper = await mountNode(buildNode({ note: 'Read me' }), {
      readOnly: true,
    })

    expect(wrapper.find('.workflow-node-content__note').exists()).toBe(true)
    expect(wrapper.find('.workflow-node-content__more-icon').exists()).toBe(
      false
    )
  })

  test('opening the note does not select the node', async () => {
    const wrapper = await mountNode(buildNode({ note: 'Read me' }))

    await wrapper.find('.workflow-node-content__note').trigger('click')

    expect(wrapper.emitted('select-node')).toBeUndefined()
  })
})
