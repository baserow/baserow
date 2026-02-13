import { getPrefills, prefillField } from '@baserow/modules/database/utils/form'

const valuesToCall = [
  {
    query: {},
    result: {},
  },
  {
    query: { someUnrelatedQuery: 'someValue' },
    result: {},
  },
  {
    query: { prefill_value: 'value' },
    result: { value: 'value' },
  },
  {
    query: { 'prefill_value+with+spaces': 'value' },
    result: { 'value with spaces': 'value' },
  },
  {
    query: { prefill_value: ['value', 'value_2'] },
    result: { value: 'value_2' },
  },
]

const prefillFieldScenarios = [
  // No value in prefill
  {
    prefills: { description: 'Some description value' },
    formField: { name: 'NameF', field: { id: '123', name: 'NameT' } },
    result: undefined,
  },
  // Value taken from form field name
  {
    prefills: { namef: 'Form name value' },
    formField: { name: 'NameF', field: { id: '123', name: 'NameT' } },
    result: 'Form name value',
  },
  // Value taken from table field name
  {
    prefills: { namet: 'Table column name value' },
    formField: { name: 'NameF', field: { id: '123', name: 'NameT' } },
    result: 'Table column name value',
  },
  // Value taken from table field id
  {
    prefills: { field_123: 'Value based on field id' },
    formField: { name: 'NameF', field: { id: '123', name: 'NameT' } },
    result: 'Value based on field id',
  },
  // Priority for form name over table name
  {
    prefills: { namef: 'Form name value', namet: 'Table column name value' },
    formField: { name: 'NameF', field: { id: '123', name: 'NameT' } },
    result: 'Form name value',
  },
  // Priority for table name over field_$ID
  {
    prefills: {
      namet: 'Table column name value',
      field_123: 'Value based on field id',
    },
    formField: { name: 'NameF', field: { id: '123', name: 'NameT' } },
    result: 'Table column name value',
  },
]

describe('Form utils test', () => {
  test.each(valuesToCall)(
    'that all values are correctly extracted from the query',
    ({ query, result }) => {
      expect(getPrefills(query)).toEqual(result)
    }
  )

  test.each(prefillFieldScenarios)(
    'Test that fields are properly prefilled with priority to form name, ' +
      'then table column name, then field id',
    ({ prefills, formField, result }) => {
      expect(prefillField(formField, prefills)).toEqual(result)
    }
  )
})
