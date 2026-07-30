import {
  NodeType,
  CoreRouterNodeType,
} from '@baserow/modules/automation/nodeTypes'
import { TestApp } from '@baserow/test/helpers/testApp'

describe('NodeType.getHistoryLabel', () => {
  class TestNodeType extends NodeType {
    static getType() {
      return 'test'
    }

    get name() {
      return 'Test node'
    }
  }

  test('uses the label the designer gave the node', () => {
    const nodeType = new TestNodeType({ app: {} })
    expect(
      nodeType.getHistoryLabel({ nodeHistory: { node_label: 'My node' } })
    ).toBe('My node')
  })

  test('falls back to the node type name when the node has no label', () => {
    const nodeType = new TestNodeType({ app: {} })
    expect(nodeType.getHistoryLabel({ nodeHistory: { node_label: '' } })).toBe(
      'Test node'
    )
  })
})

describe('CoreRouterNodeType.getHistoryLabel', () => {
  const makeApp = () => ({
    $i18n: {
      t: (key, values) => (values ? `${key}:${JSON.stringify(values)}` : key),
    },
    $registry: { get: () => ({ name: 'Router' }) },
  })

  test('appends the branch that was taken', () => {
    const nodeType = new CoreRouterNodeType({ app: makeApp() })
    expect(
      nodeType.getHistoryLabel({
        nodeHistory: { node_label: 'My router', edge_label: 'Yes' },
      })
    ).toBe('nodeType.routerHistoryLabel:{"label":"My router","edge":"Yes"}')
  })

  test('appends the fallback edge label when no branch was recorded', () => {
    const nodeType = new CoreRouterNodeType({ app: makeApp() })
    expect(
      nodeType.getHistoryLabel({
        nodeHistory: { node_label: 'My router', edge_label: '' },
      })
    ).toBe(
      'nodeType.routerHistoryLabel:{"label":"My router","edge":"nodeType.defaultEdgeLabelFallback"}'
    )
  })

  test('falls back to the node type name when the node has no label', () => {
    const nodeType = new CoreRouterNodeType({ app: makeApp() })
    expect(
      nodeType.getHistoryLabel({
        nodeHistory: { node_label: '', edge_label: 'Yes' },
      })
    ).toBe('nodeType.routerHistoryLabel:{"label":"Router","edge":"Yes"}')
  })
})

describe('Automation node types', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  test('orders workflow action nodes in the add node menu', () => {
    const nodeTypes = testApp
      .getRegistry()
      .getOrderedList('node')
      .filter((nodeType) => nodeType.isWorkflowAction)
      .map((type) => type.getType())

    expect(nodeTypes).toEqual([
      'local_baserow_create_row',
      'local_baserow_create_rows',
      'local_baserow_update_row',
      'local_baserow_update_rows',
      'local_baserow_delete_row',
      'local_baserow_get_row',
      'local_baserow_list_rows',
      'local_baserow_aggregate_rows',
      'start_workflow',
      'http_request',
      'smtp_email',
      'code',
      'iterator',
      'ai_agent',
      'router',
      'csv_file_reader',
      'xls_file_reader',
      'goto',
      'slack_write_message',
    ])
  })

  test('groups HTTP trigger and request nodes under HTTP', () => {
    const registry = testApp.getRegistry()

    expect(
      ['http_trigger', 'http_request'].map(
        (type) => registry.get('node', type).group.id
      )
    ).toEqual(['http', 'http'])
  })

  test('groups file reader nodes under Files', () => {
    const registry = testApp.getRegistry()

    expect(
      ['csv_file_reader', 'xls_file_reader'].map(
        (type) => registry.get('node', type).group.id
      )
    ).toEqual(['files', 'files'])
  })

  test('groups workflow nodes under Workflow', () => {
    const registry = testApp.getRegistry()

    expect(
      ['start_workflow', 'iterator', 'router'].map(
        (type) => registry.get('node', type).group.id
      )
    ).toEqual(['workflow', 'workflow', 'workflow'])
  })

  test('uses service-specific icons and images for workflow action nodes', () => {
    const registry = testApp.getRegistry()
    const createRow = registry.get('node', 'local_baserow_create_row')
    const updateRow = registry.get('node', 'local_baserow_update_row')
    const aiAgent = registry.get('node', 'ai_agent')
    const smtp = registry.get('node', 'smtp_email')
    const slack = registry.get('node', 'slack_write_message')

    expect([createRow.iconClass, updateRow.iconClass]).toEqual([
      'iconoir-plus',
      'iconoir-edit-pencil',
    ])
    expect([createRow.iconColor, updateRow.iconColor]).toEqual([
      'darker-blue',
      'darker-blue',
    ])
    expect([createRow.image, updateRow.image]).toEqual([undefined, undefined])
    expect(aiAgent.iconColor).toBe('var(--palette-blue-700)')
    expect(smtp.iconColor).toBe('var(--palette-red-700)')
    expect(slack.iconClass).toBe('iconoir-message-text')
    expect(slack.iconColor).toBe('darker-pink')
    expect(slack.image).toBeUndefined()
  })
})
