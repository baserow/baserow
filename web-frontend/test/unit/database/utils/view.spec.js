import {
  TreeGroupNode,
  createFiltersTree,
  matchSearchFilters,
} from '@baserow/modules/database/utils/view'
import { TestApp } from '@baserow/test/helpers/testApp'
import _ from 'lodash'

describe('TreeGroupNode', () => {
  it('should initialize correctly', () => {
    const node = new TreeGroupNode('AND')
    expect(node.filterType).toBe('AND')
    expect(node.parent).toBeNull()
    expect(node.filters).toEqual([])
    expect(node.children).toEqual([])
  })

  it('should add child nodes', () => {
    const parentNode = new TreeGroupNode('AND')
    const childNode = new TreeGroupNode('OR', parentNode)
    expect(parentNode.children[0]).toBe(childNode)
  })
})

describe('createFiltersTree', () => {
  it('should create a tree with root node', () => {
    const rootNode = createFiltersTree('AND', [], [])
    expect(rootNode.filterType).toBe('AND')
    expect(rootNode.hasFilters()).toBe(false)
    expect(rootNode.filters).toEqual([])
    expect(rootNode.children).toEqual([])
  })

  it('should correctly add filters to the tree', () => {
    const filters = [
      { field: 1, type: 'type1', value: 'value1', group: 1 },
      { field: 2, type: 'type2', value: 'value2', group: 2 },
      { field: 3, type: 'type3', value: 'value3' },
    ]
    const filterGroups = [
      { id: 1, filter_type: 'AND' },
      { id: 2, filter_type: 'OR' },
      { id: 3, filter_type: 'AND' },
    ]
    const rootNode = createFiltersTree('AND', filters, filterGroups)
    expect(rootNode.filterType).toBe('AND')
    expect(rootNode.hasFilters()).toBe(true)
    expect(rootNode.filters).toEqual([
      { field: 3, type: 'type3', value: 'value3' },
    ])
    expect(rootNode.children).toHaveLength(3)
    expect(rootNode.children[0].filterType).toBe('AND')
    expect(rootNode.children[0].filters).toEqual([
      { field: 1, type: 'type1', value: 'value1', group: 1 },
    ])
    expect(rootNode.children[0].children).toEqual([])
    expect(rootNode.children[1].filterType).toBe('OR')
    expect(rootNode.children[1].filters).toEqual([
      { field: 2, type: 'type2', value: 'value2', group: 2 },
    ])
    expect(rootNode.children[2].filters).toEqual([])
    expect(rootNode.children[2].hasFilters()).toBe(false)
  })

  it('should correctly nest groups into the tree', () => {
    const filterGroups = [
      { id: 1, filter_type: 'AND' },
      { id: 2, filter_type: 'OR', parent_group: 1 },
      { id: 3, filter_type: 'AND', parent_group: 1 },
      { id: 4, filter_type: 'OR', parent_group: 3 },
    ]
    const rootNode = createFiltersTree('AND', [], filterGroups)
    expect(rootNode.hasFilters()).toBe(false)
    expect(rootNode.children).toHaveLength(1)
    expect(rootNode.children[0].filterType).toBe('AND')
    expect(rootNode.children[0].children).toHaveLength(2)
    expect(rootNode.children[0].children[0].filterType).toBe('OR')
    expect(rootNode.children[0].children[0].children).toEqual([])
    expect(rootNode.children[0].children[1].filterType).toBe('AND')
    expect(rootNode.children[0].children[1].children).toHaveLength(1)
    expect(rootNode.children[0].children[1].children[0].filterType).toBe('OR')
    expect(rootNode.children[0].children[1].children[0].children).toEqual([])
  })

  it('should correctly add filters to nested groups', () => {
    const filterGroups = [
      { id: 1, filter_type: 'AND' },
      { id: 2, filter_type: 'OR', parent_group: 1 },
      { id: 3, filter_type: 'OR', parent_group: 2 },
    ]
    const rootNode = createFiltersTree('AND', [], filterGroups)
    expect(rootNode.hasFilters()).toBe(false)
    rootNode.children[0].children[0].children[0].addFilter({
      field: 1,
      type: 'type1',
      value: 'value1',
      group: 4,
    })
    expect(rootNode.hasFilters()).toBe(true)
  })
})

describe('matchSearchFilters', () => {
  let testApp = null
  let registry = null

  beforeEach(() => {
    testApp = new TestApp()
    registry = testApp.getRegistry()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  it.skip('should return true with no filters', () => {
    const filters = []
    const filterGroups = []
    const fields = {}
    const rowValues = {}
    expect(
      matchSearchFilters(
        registry,
        'AND',
        filters,
        filterGroups,
        fields,
        rowValues
      )
    ).toBe(true)
  })

  it('should match a single filter', () => {
    const filters = [{ field: 1, type: 'equal', value: 'a' }]
    const filterGroups = []
    const fields = [{ id: 1, type: 'text' }]
    expect(
      matchSearchFilters('AND', filters, filterGroups, fields, {
        field_1: 'a',
      })
    ).toBe(true)

    expect(
      matchSearchFilters('AND', filters, filterGroups, fields, {
        field_1: 'b',
      })
    ).toBe(false)
  })

  it('should match a single filter in a group', () => {
    const filters = [{ field: 1, type: 'equal', value: 'a', group: 1 }]
    const filterGroups = [{ filter_type: 'OR', id: 1 }]
    const fields = [{ id: 1, type: 'text' }]
    expect(
      matchSearchFilters('AND', filters, filterGroups, fields, {
        field_1: 'a',
      })
    ).toBe(true)
    expect(
      matchSearchFilters('AND', filters, filterGroups, fields, {
        field_1: 'b',
      })
    ).toBe(false)
  })

  it('should match filters correctly with OR and AND', () => {
    // Match rows where field_1=Ada OR (field_1=John AND field_2=Turing)
    const filters = [
      { field: 1, type: 'equal', value: 'Ada' },
      { field: 1, type: 'equal', value: 'John', group: 1 },
      { field: 2, type: 'equal', value: 'Turing', group: 1 },
    ]
    const filterGroups = [{ filter_type: 'AND', id: 1 }]
    const fields = [
      { id: 1, type: 'text' },
      { id: 2, type: 'text' },
    ]

    expect(
      matchSearchFilters('OR', filters, filterGroups, fields, {
        field_1: 'Ada',
        field_2: 'Lovelace',
      })
    ).toBe(true)

    expect(
      matchSearchFilters('OR', filters, filterGroups, fields, {
        field_1: 'Alan',
        field_2: 'Turing',
      })
    ).toBe(false)

    expect(
      matchSearchFilters('OR', filters, filterGroups, fields, {
        field_1: 'John',
        field_2: 'Travolta',
      })
    ).toBe(false)

    expect(
      matchSearchFilters('OR', filters, filterGroups, fields, {
        field_1: 'John',
        field_2: 'Turing',
      })
    ).toBe(true)
  })

  it('should match filters correctly with AND and OR', () => {
    // Match rows where field_1=John AND (field_2=Travolta OR field_2=Turing)
    const filters = [
      { field: 1, type: 'equal', value: 'John' },
      { field: 2, type: 'equal', value: 'Travolta', group: 1 },
      { field: 2, type: 'equal', value: 'Turing', group: 1 },
    ]
    const filterGroups = [{ filter_type: 'OR', id: 1 }]
    const fields = [
      { id: 1, type: 'text' },
      { id: 2, type: 'text' },
    ]

    expect(
      matchSearchFilters('AND', filters, filterGroups, fields, {
        field_1: 'John',
        field_2: 'Lennon',
      })
    ).toBe(false)

    expect(
      matchSearchFilters('AND', filters, filterGroups, fields, {
        field_1: 'Alan',
        field_2: 'Turing',
      })
    ).toBe(false)

    expect(
      matchSearchFilters('AND', filters, filterGroups, fields, {
        field_1: 'John',
        field_2: 'Travolta',
      })
    ).toBe(true)

    expect(
      matchSearchFilters('AND', filters, filterGroups, fields, {
        field_1: 'John',
        field_2: 'Turing',
      })
    ).toBe(true)
  })

  it('should serialize the filter tree correctly', () => {
    const filters = [
      { field: 1, type: 'equal', value: 'a' },
      { field: 2, type: 'equal', value: 'b', group: 1 },
      { field: 3, type: 'equal', value: 'c', group: 1 },
    ]
    const filterGroups = [{ filter_type: 'OR', id: 1 }]
    const rootNode = createFiltersTree('AND', filters, filterGroups)
    expect(
      _.isEqual(rootNode.getFiltersTreeSerialized(), {
        filter_type: 'AND',
        filters: [{ type: 'equal', field: 1, value: 'a' }],
        groups: [
          {
            filter_type: 'OR',
            filters: [
              { type: 'equal', field: 2, value: 'b' },
              { type: 'equal', field: 3, value: 'c' },
            ],
            groups: [],
          },
        ],
      })
    ).toBe(true)
  })
})
