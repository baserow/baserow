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
})
