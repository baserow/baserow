import { TestApp } from '@baserow/test/helpers/testApp'
import {
  DATA_PROVIDERS_ALLOWED_NODE_ACTIONS,
  DATA_PROVIDERS_ALLOWED_RETRY_CONDITION,
} from '@baserow/modules/automation/enums'

describe('CurrentNodeDataProviderType', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const provider = () =>
    testApp.getRegistry().get('automationDataProvider', 'current_node')

  const objectSchema = {
    type: 'object',
    properties: {
      status_code: { type: 'number', title: 'Status code' },
      body: { type: 'object', title: 'Body', properties: {} },
    },
  }

  // The path carries no node id: the provider offers the node's own result
  // under its own name, whatever the node is called.
  test('offers the result of an object node under its own title', () => {
    const node = {
      id: 1,
      type: 'http_request',
      label: 'Fetch',
      service: { schema: objectSchema },
    }

    const schema = provider().getDataSchema({ automation: {}, node })

    expect(schema.type).toBe('object')
    expect(schema.properties).toStrictEqual(objectSchema.properties)
    expect(schema.title).toBe('dataProviderType.currentNode')
    expect(provider().name).toBe('dataProviderType.currentNode')
  })

  test('offers the rows of a list node', () => {
    const listSchema = {
      type: 'array',
      items: {
        type: 'object',
        properties: { id: { type: 'number', title: 'Id' } },
      },
    }
    const node = {
      id: 2,
      type: 'local_baserow_list_rows',
      label: 'Rows',
      service: { schema: listSchema },
    }

    const schema = provider().getDataSchema({ automation: {}, node })

    expect(schema.type).toBe('array')
    expect(schema.items).toStrictEqual(listSchema.items)
    expect(schema.title).toBe('dataProviderType.currentNode')
  })

  test('has nothing to offer without a service schema', () => {
    const automation = {}

    expect(
      provider().getDataSchema({
        automation,
        node: { id: 3, type: 'http_request', label: 'Fetch', service: null },
      })
    ).toBeNull()
    expect(
      provider().getDataSchema({
        automation,
        node: {
          id: 4,
          type: 'http_request',
          label: 'Fetch',
          service: { schema: null },
        },
      })
    ).toBeNull()
    expect(provider().getDataSchema({ automation, node: {} })).toBeNull()
  })

  test('is offered to the retry condition and nowhere else', () => {
    expect(DATA_PROVIDERS_ALLOWED_RETRY_CONDITION).toEqual([
      'current_node',
      ...DATA_PROVIDERS_ALLOWED_NODE_ACTIONS,
    ])
    expect(DATA_PROVIDERS_ALLOWED_NODE_ACTIONS).not.toContain('current_node')
  })
})
