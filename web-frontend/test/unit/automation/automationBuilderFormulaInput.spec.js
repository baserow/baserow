import { vi } from 'vitest'
import { TestApp } from '@baserow/test/helpers/testApp'
import AutomationBuilderFormulaInput from '@baserow/modules/automation/components/AutomationBuilderFormulaInput'

const FormulaInputFieldStub = {
  name: 'FormulaInputField',
  props: { nodesHierarchy: { type: Array, default: () => [] } },
  template: '<div />',
}

describe('AutomationBuilderFormulaInput sample values', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const previousNode = {
    id: 1,
    type: 'http_request',
    label: 'Fetch',
    service: {
      schema: {
        type: 'object',
        properties: { status_code: { type: 'number', title: 'Status code' } },
      },
      sample_data: { data: { status_code: 200 } },
    },
  }
  const workflow = { nodes: [previousNode], nodeMap: { 1: previousNode } }

  async function mountInput(dataProvidersAllowed) {
    const registry = testApp.getRegistry()
    for (const type of dataProvidersAllowed) {
      // The graph isn't under test: each provider offers the previous node.
      vi.spyOn(
        registry.get('automationDataProvider', type),
        'getDataSchema'
      ).mockReturnValue({
        type: 'object',
        properties: { 1: { ...previousNode.service.schema, title: 'Fetch' } },
      })
    }
    const wrapper = await testApp.mount(AutomationBuilderFormulaInput, {
      props: { dataProvidersAllowed },
      global: {
        provide: { applicationContext: { workflow, node: { id: 2 } } },
        stubs: { FormulaInputField: FormulaInputFieldStub },
      },
    })
    return wrapper
      .findComponent(FormulaInputFieldStub)
      .props('nodesHierarchy')
      .find(({ type }) => type === 'data')
  }

  test('gives the explorer the value of a data node path', async () => {
    const { getValue } = await mountInput(['previous_node'])

    expect(getValue('previous_node.1.status_code')).toBe(200)
    expect(getValue('previous_node.1.missing')).toBeUndefined()
    expect(getValue('previous_node.1')).toBeUndefined()
  })

  test('has no value for a provider that is not offered', async () => {
    const { getValue } = await mountInput(['previous_node'])

    expect(getValue('current_iteration.1.item')).toBeUndefined()
    expect(getValue('unknown.1.status_code')).toBeUndefined()
  })
})
