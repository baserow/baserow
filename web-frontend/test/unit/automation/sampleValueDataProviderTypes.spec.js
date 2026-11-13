import { vi } from 'vitest'
import { TestApp } from '@baserow/test/helpers/testApp'

describe('Automation data providers sample values', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const provider = (type) =>
    testApp.getRegistry().get('automationDataProvider', type)

  const workflowWith = (...nodes) => ({
    nodes,
    nodeMap: Object.fromEntries(nodes.map((node) => [`${node.id}`, node])),
  })

  const objectNode = (overrides = {}) => ({
    id: 1,
    type: 'http_request',
    label: 'Fetch',
    service: {
      schema: {
        type: 'object',
        properties: {
          status_code: { type: 'number', title: 'Status code' },
          body: { type: 'object', title: 'Body', properties: {} },
        },
      },
      sample_data: {
        data: {
          status_code: 200,
          body: { user: { name: 'Ada' }, note: '', deleted_at: null },
        },
        status: 200,
      },
      ...overrides,
    },
  })

  const listNode = (overrides = {}) => ({
    id: 2,
    type: 'local_baserow_list_rows',
    label: 'Rows',
    service: {
      schema: {
        type: 'array',
        items: {
          type: 'object',
          properties: {
            id: { type: 'number', title: 'Id' },
            field_10: { type: 'string', title: 'Name' },
          },
        },
      },
      sample_data: {
        data: {
          results: [
            { id: 1, Name: 'Acme' },
            { id: 2, Name: 'Globex' },
          ],
          has_next_page: false,
        },
      },
      ...overrides,
    },
  })

  describe('previous_node', () => {
    test('reads a value from the last test of an object node', () => {
      const workflow = workflowWith(objectNode())
      const chunk = (path) =>
        provider('previous_node').getSampleValue({ workflow }, path)

      expect(chunk(['1', 'status_code'])).toBe(200)
      expect(chunk(['1', 'body', 'user', 'name'])).toBe('Ada')
      expect(chunk(['1', 'body', 'note'])).toBe('')
      // A value that is known to be empty is not the same as no value.
      expect(chunk(['1', 'body', 'deleted_at'])).toBeNull()
      expect(chunk(['1', 'body'])).toStrictEqual({
        user: { name: 'Ada' },
        note: '',
        deleted_at: null,
      })
    })

    test('reads rows by index and maps field ids to their names', () => {
      const workflow = workflowWith(listNode())
      const chunk = (path) =>
        provider('previous_node').getSampleValue({ workflow }, path)

      expect(chunk(['2', '0', 'field_10'])).toBe('Acme')
      expect(chunk(['2', '1', 'field_10'])).toBe('Globex')
      expect(chunk(['2', '1', 'id'])).toBe(2)
      expect(chunk(['2', '*', 'field_10'])).toStrictEqual(['Acme', 'Globex'])
      expect(chunk(['2', '0'])).toStrictEqual({ id: 1, Name: 'Acme' })
    })

    test('has no value for what the sample does not hold', () => {
      const workflow = workflowWith(objectNode(), listNode())
      const chunk = (path) =>
        provider('previous_node').getSampleValue({ workflow }, path)

      // The node itself is a heading.
      expect(chunk(['1'])).toBeUndefined()
      // Unknown node, unknown key, index out of the sample, and a path that
      // runs through a value that is not an object.
      expect(chunk(['99', 'status_code'])).toBeUndefined()
      expect(chunk(['1', 'missing'])).toBeUndefined()
      expect(chunk(['2', '5', 'field_10'])).toBeUndefined()
      expect(chunk(['1', 'status_code', 'deeper'])).toBeUndefined()
    })

    test('has no value for a node that is untested or failed its test', () => {
      const untested = objectNode({ sample_data: null })
      const failed = {
        ...objectNode({ sample_data: { _error: 'Boom' } }),
        id: 3,
      }
      const workflow = workflowWith(untested, failed)
      const chunk = (path) =>
        provider('previous_node').getSampleValue({ workflow }, path)

      expect(chunk(['1', 'status_code'])).toBeUndefined()
      expect(chunk(['3', 'status_code'])).toBeUndefined()
    })

    test('adds a hint to the nodes without values only', () => {
      const tested = objectNode()
      const untested = { ...objectNode({ sample_data: null }), id: 3 }
      const failed = {
        ...objectNode({ sample_data: { _error: 'Boom' } }),
        id: 4,
      }
      const workflow = workflowWith(tested, untested, failed)
      const dataProvider = provider('previous_node')
      vi.spyOn(dataProvider, 'getDataSchema').mockReturnValue({
        type: 'object',
        properties: Object.fromEntries(
          [tested, untested, failed].map((node) => [
            node.id,
            { ...node.service.schema, title: `Fetch ${node.id}` },
          ])
        ),
      })

      const { nodes } = dataProvider.getNodes({ workflow })

      expect(nodes.map(({ identifier, hint }) => [identifier, hint])).toEqual([
        ['1', undefined],
        ['3', 'dataProviderType.testToSeeValues'],
        ['4', 'dataProviderType.testToSeeValues'],
      ])
    })
  })

  describe('current_iteration', () => {
    test('offers the first item of the parent as an example', () => {
      const workflow = workflowWith(listNode())
      const chunk = (path) =>
        provider('current_iteration').getSampleValue({ workflow }, path)

      expect(chunk(['2', 'index'])).toBe(0)
      expect(chunk(['2', 'item'])).toStrictEqual({ id: 1, Name: 'Acme' })
      expect(chunk(['2', 'item', 'id'])).toBe(1)
      expect(chunk(['2'])).toBeUndefined()
    })

    test('has no value when the parent returned nothing or is untested', () => {
      const empty = listNode({
        sample_data: { data: { results: [], has_next_page: false } },
      })
      const untested = { ...listNode({ sample_data: null }), id: 3 }
      const workflow = workflowWith(empty, untested)
      const chunk = (path) =>
        provider('current_iteration').getSampleValue({ workflow }, path)

      expect(chunk(['2', 'item', 'id'])).toBeUndefined()
      expect(chunk(['2', 'index'])).toBeUndefined()
      expect(chunk(['3', 'item', 'id'])).toBeUndefined()
    })
  })

  describe('current_node', () => {
    test('reads a value from the last test of the edited node', () => {
      const chunk = (node, path) =>
        provider('current_node').getSampleValue({ node }, path)

      expect(chunk(objectNode(), ['status_code'])).toBe(200)
      expect(chunk(objectNode({ sample_data: null }), ['status_code'])).toBe(
        undefined
      )
      expect(chunk({}, ['status_code'])).toBeUndefined()
    })
  })
})
