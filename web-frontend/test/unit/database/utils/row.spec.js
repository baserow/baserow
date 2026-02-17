import {
  prepareRowForRequest,
  prepareNewOldAndUpdateRequestValues,
  extractRowReadOnlyValues,
  mergeRowMetadata,
  updateRowMetadataType,
} from '@baserow/modules/database/utils/row'
import { TestApp } from '@baserow/test/helpers/testApp'

describe('Row utilities', () => {
  let testApp = null
  let store = null

  beforeEach(() => {
    testApp = new TestApp()
    store = testApp.store
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  describe('prepareRowForRequest', () => {
    const rowsToTest = [
      // Empty case
      {
        input: {
          row: {},
          fields: [],
        },
        output: {},
      },
      // Basic case of just a simple text field
      {
        input: {
          row: {
            field_1: 'value',
          },
          fields: [
            {
              name: 'field_1',
              id: 1,
              type: 'text',
            },
          ],
        },
        output: {
          field_1: 'value',
        },
      },
      // Empty value is being used if no value is provided
      {
        input: {
          row: {
            field_1: 'value',
          },
          fields: [
            {
              name: 'field_1',
              id: 1,
              type: 'text',
            },
            {
              name: 'field_2',
              id: 2,
              text_default: 'some default',
              type: 'text',
            },
          ],
        },
        output: {
          field_1: 'value',
          field_2: 'some default',
        },
      },
      // Read only field
      {
        input: {
          row: {
            field_1: 'value',
          },
          fields: [
            {
              name: 'field_1',
              id: 1,
              type: 'formula',
            },
          ],
        },
        output: {},
      },
      // Missing value
      {
        input: {
          row: {},
          fields: [
            {
              name: 'field_1',
              id: 1,
              text_default: 'some default',
              type: 'text',
            },
          ],
        },
        output: {
          field_1: 'some default',
        },
      },
    ]

    test.each(rowsToTest)(
      'that %o is correctly prepared for request',
      ({ input, output }) => {
        expect(
          prepareRowForRequest(input.row, input.fields, store.$registry)
        ).toEqual(output)
      },
      200
    )
  })

  test('prepareNewOldAndUpdateRequestValues', () => {
    const row = {
      id: 1,
      field_1: { id: 2, value: 'Option 2', color: 'green' },
      field_2: '2024-01-04T15:15:59.163126Z',
      field_3: 'Text',
    }
    const allFields = [
      {
        id: 1,
        name: 'Single Select',
        type: 'single_select',
        select_options: [
          {
            id: 1,
            value: 'Option 1',
            color: 'blue',
          },
          {
            id: 2,
            value: 'Option 2',
            color: 'green',
          },
        ],
      },
      {
        id: 2,
        name: 'Last modified',
        type: 'last_modified',
        date_include_time: true,
      },
      {
        id: 3,
        name: 'Text',
        type: 'text',
      },
    ]
    const field = allFields[0]
    const value = { id: 1, value: 'Option 1', color: 'blue' }
    const oldValue = { id: 2, value: 'Option 2', color: 'green' }

    const { newRowValues, oldRowValues, updateRequestValues } =
      prepareNewOldAndUpdateRequestValues(
        row,
        allFields,
        field,
        value,
        oldValue,
        store.$registry
      )

    expect(newRowValues.field_2).not.toBe(oldRowValues.field_2)
    expect(newRowValues).toEqual({
      id: row.id,
      field_1: { id: 1, value: 'Option 1', color: 'blue' },
      field_2: newRowValues.field_2,
    })
    expect(oldRowValues).toEqual({
      id: row.id,
      field_1: { id: 2, value: 'Option 2', color: 'green' },
      field_2: '2024-01-04T15:15:59.163126Z',
    })
    expect(updateRequestValues).toEqual({
      field_1: 1,
      id: row.id,
    })
  })

  test('extractRowReadOnlyValues', () => {
    const row = {
      id: 1,
      field_2: '2024-01-04T15:15:59.163126Z',
      field_3: 'Text',
    }
    const allFields = [
      {
        id: 2,
        name: 'Last modified',
        type: 'last_modified',
        date_include_time: true,
      },
      {
        id: 3,
        name: 'Text',
        type: 'text',
      },
    ]

    const newRow = extractRowReadOnlyValues(row, allFields, store.$registry)

    expect(newRow).toEqual({
      id: 1,
      field_2: '2024-01-04T15:15:59.163126Z',
    })
  })
})

describe('mergeRowMetadata', () => {
  test('merges new type into empty existing metadata', () => {
    const result = mergeRowMetadata(
      {},
      { ai_field: { 1: { status: 'generating' } } }
    )
    expect(result).toEqual({ ai_field: { 1: { status: 'generating' } } })
  })

  test('deep merges field keys within a metadata type', () => {
    const existing = { ai_field: { 1: { status: 'error' } } }
    const result = mergeRowMetadata(existing, {
      ai_field: { 2: { status: 'generating' } },
    })
    expect(result.ai_field[1]).toEqual({ status: 'error' })
    expect(result.ai_field[2]).toEqual({ status: 'generating' })
  })

  test('overwrites existing field key with new value', () => {
    const existing = { ai_field: { 1: { status: 'error' } } }
    const result = mergeRowMetadata(existing, {
      ai_field: { 1: { status: 'generating' } },
    })
    expect(result.ai_field[1]).toEqual({ status: 'generating' })
  })

  test('removes field keys set to null', () => {
    const existing = {
      ai_field: { 1: { status: 'error' }, 2: { status: 'ok' } },
    }
    const result = mergeRowMetadata(existing, { ai_field: { 1: null } })
    expect(result.ai_field[1]).toBeUndefined()
    expect(result.ai_field[2]).toEqual({ status: 'ok' })
  })

  test('preserves unrelated metadata types', () => {
    const existing = { row_comment_count: { count: 5 } }
    const result = mergeRowMetadata(existing, {
      ai_field: { 1: { status: 'generating' } },
    })
    expect(result.row_comment_count).toEqual({ count: 5 })
    expect(result.ai_field[1]).toEqual({ status: 'generating' })
  })

  test('returns new object without mutating inputs', () => {
    const existing = { ai_field: { 1: { status: 'error' } } }
    const result = mergeRowMetadata(existing, {
      ai_field: { 1: { status: 'generating' } },
    })
    expect(result).not.toBe(existing)
    expect(existing.ai_field[1]).toEqual({ status: 'error' })
  })
})

describe('updateRowMetadataType', () => {
  test('updates specific metadata type via callback', () => {
    const row = {
      _: { metadata: { ai_field: { 1: { status: 'error' } } } },
    }
    updateRowMetadataType(row, 'ai_field', () => ({
      1: { status: 'generating' },
    }))
    expect(row._.metadata.ai_field).toEqual({ 1: { status: 'generating' } })
  })

  test('passes current value to callback', () => {
    const row = {
      _: { metadata: { ai_field: { 1: { status: 'error' } } } },
    }
    updateRowMetadataType(row, 'ai_field', (current) => {
      expect(current).toEqual({ 1: { status: 'error' } })
      return { 1: { status: 'generating' } }
    })
  })

  test('creates row._ structure if missing', () => {
    const row = {}
    updateRowMetadataType(row, 'ai_field', () => ({ 1: { status: 'ok' } }))
    expect(row._.metadata.ai_field).toEqual({ 1: { status: 'ok' } })
  })

  test('preserves other metadata types', () => {
    const row = {
      _: { metadata: { row_comment_count: 5, ai_field: { old: true } } },
    }
    updateRowMetadataType(row, 'ai_field', () => ({ new: true }))
    expect(row._.metadata.row_comment_count).toBe(5)
    expect(row._.metadata.ai_field).toEqual({ new: true })
  })
})
