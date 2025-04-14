import { TestApp } from '@baserow/test/helpers/testApp'
import {
  BooleanFieldType,
  DateFieldType,
  DurationFieldType,
  EmailFieldType,
  LinkRowFieldType,
  LongTextFieldType,
  MultipleSelectFieldType,
  NumberFieldType,
  PhoneNumberFieldType,
  RatingFieldType,
  SingleSelectFieldType,
  TextFieldType,
  URLFieldType,
} from '@baserow/modules/database/fieldTypes'
import { DEFAULT_FORM_VIEW_FIELD_COMPONENT_KEY } from '@baserow/modules/database/constants'

// The `testing_row_data` is not actually part of the field instance, but it
// contains an example of how the cell value could be in the frontend.
const mockedFields = {
  text: {
    id: 1,
    name: 'text',
    order: 1,
    primary: true,
    table_id: 42,
    type: 'text',
    testing_row_data: ['test', ''],
  },
  long_text: {
    id: 2,
    name: 'long_text',
    order: 2,
    primary: false,
    table_id: 42,
    type: 'long_text',
    testing_row_data: ['test', ''],
  },
  link_row: {
    id: 3,
    name: 'link_row',
    order: 3,
    primary: false,
    table_id: 42,
    type: 'link_row',
    link_row_related_field: 270,
    link_row_table_id: 43,
    link_row_table_primary_field: {
      id: 270,
      name: 'name',
      order: 1,
      primary: true,
      table_id: 43,
      type: 'text',
    },
    testing_row_data: [
      [],
      [{ id: 1, value: 'Row 1' }],
      [
        { id: 1, value: 'Row 1' },
        { id: 2, value: 'Row 2' },
      ],
    ],
  },
  number: {
    id: 4,
    name: 'number',
    order: 4,
    primary: false,
    table_id: 42,
    type: 'number',
    number_decimal_places: 0,
    number_negative: false,
    testing_row_data: [null, '10', '20'],
  },
  rating: {
    id: 16,
    name: 'rating',
    order: 4,
    primary: false,
    table_id: 42,
    type: 'rating',
    testing_row_data: [0, 1, 3],
  },
  boolean: {
    id: 5,
    name: 'boolean',
    order: 5,
    primary: false,
    table_id: 42,
    type: 'boolean',
    testing_row_data: [true, false],
  },
  date: {
    id: 6,
    name: 'date',
    order: 6,
    primary: false,
    table_id: 42,
    type: 'date',
    date_format: 'EU',
    date_include_time: false,
    date_time_format: '24',
    testing_row_data: [null, '2023-10-05T02:00:00+02:00'],
  },
  last_modified: {
    id: 7,
    name: 'last_modified',
    order: 7,
    primary: false,
    table_id: 42,
    type: 'last_modified',
    date_format: 'EU',
    date_include_time: false,
    date_time_format: '24',
    testing_row_data: ['2023-10-05T02:00:00+02:00'],
  },
  created_on: {
    id: 8,
    name: 'created_on',
    order: 8,
    primary: false,
    table_id: 42,
    type: 'created_on',
    date_format: 'EU',
    date_include_time: false,
    date_time_format: '24',
    testing_row_data: ['2023-10-05T02:00:00+02:00'],
  },
  url: {
    id: 9,
    name: 'url',
    order: 9,
    primary: false,
    table_id: 42,
    type: 'url',
    testing_row_data: ['', 'https://baserow.io'],
  },
  email: {
    id: 10,
    name: 'email',
    order: 10,
    primary: false,
    table_id: 42,
    type: 'email',
    testing_row_data: ['', 'bram@baserow.io'],
  },
  file: {
    id: 11,
    name: 'file',
    order: 11,
    primary: false,
    table_id: 42,
    type: 'file',
    testing_row_data: [
      [],
      [
        {
          url: 'http://localhost:4000/media/user_files/k03pSb0YtDIUzwHZ6aZaRl9ufGgKROcX_9a2270d5964f64981fb1e91dd13e5941262817bdce873cf357c92adbef906b5d.mp3',
          thumbnails: null,
          visible_name: 'file_example_MP3_700KB.mp3',
          name: 'k03pSb0YtDIUzwHZ6aZaRl9ufGgKROcX_9a2270d5964f64981fb1e91dd13e5941262817bdce873cf357c92adbef906b5d.mp3',
          size: 733645,
          mime_type: 'audio/mpeg',
          is_image: false,
          image_width: null,
          image_height: null,
          uploaded_at: '2023-12-12T21:20:16.484349+00:00',
        },
        {
          url: 'http://localhost:4000/media/user_files/RYrdxidUTNQ8QoE5DxqgVZNyJhHbYCuV_88aeb1f4467bd1e50cf624de972fbf3f40801632fedb64aaa7b1a8a9ef786fc6.jpg',
          thumbnails: {
            tiny: {
              url: 'http://localhost:4000/media/thumbnails/tiny/RYrdxidUTNQ8QoE5DxqgVZNyJhHbYCuV_88aeb1f4467bd1e50cf624de972fbf3f40801632fedb64aaa7b1a8a9ef786fc6.jpg',
              width: null,
              height: 21,
            },
            small: {
              url: 'http://localhost:4000/media/thumbnails/small/RYrdxidUTNQ8QoE5DxqgVZNyJhHbYCuV_88aeb1f4467bd1e50cf624de972fbf3f40801632fedb64aaa7b1a8a9ef786fc6.jpg',
              width: 48,
              height: 48,
            },
            card_cover: {
              url: 'http://localhost:4000/media/thumbnails/card_cover/RYrdxidUTNQ8QoE5DxqgVZNyJhHbYCuV_88aeb1f4467bd1e50cf624de972fbf3f40801632fedb64aaa7b1a8a9ef786fc6.jpg',
              width: 300,
              height: 160,
            },
          },
          visible_name: 'file_example_JPG_100kB.jpg',
          name: 'RYrdxidUTNQ8QoE5DxqgVZNyJhHbYCuV_88aeb1f4467bd1e50cf624de972fbf3f40801632fedb64aaa7b1a8a9ef786fc6.jpg',
          size: 102117,
          mime_type: 'image/jpeg',
          is_image: true,
          image_width: 1050,
          image_height: 700,
          uploaded_at: '2023-12-12T21:20:16.490292+00:00',
        },
      ],
    ],
  },
  single_select: {
    id: 12,
    name: 'single_select',
    order: 12,
    primary: false,
    table_id: 42,
    type: 'single_select',
    select_options: [],
    testing_row_data: [null, { id: 1, value: 'Option 1', color: 'green' }],
  },
  phone_number: {
    id: 13,
    name: 'phone_number',
    order: 13,
    primary: false,
    table_id: 42,
    type: 'phone_number',
    testing_row_data: ['', '+12345678'],
  },
  multiple_select: {
    id: 14,
    name: 'multiple_select',
    order: 14,
    primary: false,
    table_id: 42,
    type: 'multiple_select',
    select_options: [],
    testing_row_data: [
      [],
      [{ id: 1, value: 'Option 1', color: 'green' }],
      [
        { id: 1, value: 'Option 1', color: 'green' },
        { id: 2, value: 'Option 2', color: 'blue' },
      ],
    ],
  },
  formula: {
    id: 15,
    name: 'formula',
    order: 16,
    primary: false,
    table_id: 42,
    type: 'formula',
    formula_type: 'text',
  },
  lookup: {
    id: 16,
    name: 'lookup',
    order: 16,
    primary: false,
    table_id: 42,
    type: 'lookup',
    formula_type: 'text',
  },
  multiple_collaborators: {
    id: 17,
    name: 'multiple_collaborators',
    order: 17,
    primary: false,
    table_id: 42,
    type: 'multiple_collaborators',
    testing_row_data: [
      [],
      [{ id: 1, name: 'Test' }],
      [
        { id: 1, name: 'Test' },
        { id: 2, name: 'Test 2' },
      ],
    ],
  },
  count: {
    id: 18,
    name: 'count',
    order: 18,
    primary: false,
    table_id: 42,
    type: 'count',
    formula_type: 'number',
  },
  rollup: {
    id: 19,
    name: 'rollup',
    order: 19,
    primary: false,
    table_id: 42,
    type: 'rollup',
    formula_type: 'text',
  },
  uuid: {
    id: 20,
    name: 'uuid',
    order: 20,
    primary: false,
    table_id: 42,
    type: 'uuid',
    testing_row_data: ['03114cab-64c6-4d27-839d-3ff6f6cb118c'],
  },
  last_modified_by: {
    id: 21,
    name: 'last_modified_by',
    order: 21,
    primary: false,
    table_id: 42,
    type: 'last_modified_by',
    testing_row_data: [null, { id: 1, name: 'Test' }],
  },
  created_by: {
    id: 22,
    name: 'created_by',
    order: 22,
    primary: false,
    table_id: 42,
    type: 'created_by',
    testing_row_data: [null, { id: 1, name: 'Test' }],
  },
  autonumber: {
    id: 23,
    name: 'autonumber',
    order: 23,
    primary: false,
    table_id: 42,
    type: 'autonumber',
    testing_row_data: [1, 2],
  },
  duration: {
    id: 24,
    name: 'duration',
    order: 24,
    primary: false,
    table_id: 42,
    type: 'duration',
    testingRowData: [null, 60],
  },
  password: {
    id: 25,
    name: 'password',
    order: 25,
    primary: false,
    table_id: 42,
    type: 'password',
    testingRowData: [null, true, 'test'],
  },
}

const valuesToCall = [null, undefined]

const datePrepareValueForCopy = [
  {
    fieldValue: '2021-12-04T10:57:22.184611Z',
    field: {
      date_format: 'EU',
      date_include_time: true,
      date_time_format: '24',
    },
    expectedValue: '04/12/2021 10:57',
  },
  {
    fieldValue: '2021-12-07T00:00:00',
    field: {
      date_format: 'US',
      date_include_time: false,
    },
    expectedValue: '12/07/2021',
  },
  {
    fieldValue: '2021-12-08T16:06:38.684274Z',
    field: {
      date_format: 'ISO',
      date_include_time: true,
      date_time_format: '12',
    },
    expectedValue: '2021-12-08 04:06 PM',
  },
]

const datePrepareValueForPaste = [
  // Date field with EU format
  {
    fieldValue: '04/12/2021',
    field: {
      date_format: 'EU',
    },
    expectedValue: '2021-12-04',
  },
  {
    fieldValue: '04/12/2021 22:57',
    field: {
      date_format: 'EU',
      date_include_time: true,
    },
    expectedValue: '2021-12-04T22:57:00Z',
  },
  {
    fieldValue: '04/12/2021 10:57 PM',
    field: {
      date_format: 'EU',
      date_include_time: true,
    },
    expectedValue: '2021-12-04T22:57:00Z',
  },
  {
    fieldValue: '2021-12-04',
    field: {
      date_format: 'EU',
    },
    expectedValue: '2021-12-04',
  },
  {
    fieldValue: '2021-12-04 22:57',
    field: {
      date_format: 'EU',
      date_include_time: true,
    },
    expectedValue: '2021-12-04T22:57:00Z',
  },
  {
    fieldValue: '2021-12-04 10:57 PM',
    field: {
      date_format: 'EU',
      date_include_time: true,
    },
    expectedValue: '2021-12-04T22:57:00Z',
  },
  {
    fieldValue: '2021-12-04T22:57:00Z',
    field: {
      date_format: 'EU',
      date_include_time: true,
    },
    expectedValue: '2021-12-04T22:57:00Z',
  },
  {
    fieldValue: '04/16/2021', // Explicit US date in EU field
    field: {
      date_format: 'EU',
    },
    expectedValue: '2021-04-16',
  },
  // Date field with US format
  {
    fieldValue: '04/12/2021',
    field: {
      date_format: 'US',
    },
    expectedValue: '2021-04-12',
  },
  {
    fieldValue: '04/12/2021 22:57',
    field: {
      date_format: 'US',
      date_include_time: true,
    },
    expectedValue: '2021-04-12T22:57:00Z',
  },
  {
    fieldValue: '04/12/2021 10:57 PM',
    field: {
      date_format: 'US',
      date_include_time: true,
    },
    expectedValue: '2021-04-12T22:57:00Z',
  },
]

const queryParametersForParsing = [
  {
    fieldType: new TextFieldType(),
    input: { value: 'test', field: {} },
    output: 'test',
  },
  {
    fieldType: new LongTextFieldType(),
    input: { value: 'test', field: {} },
    output: 'test',
  },
  {
    fieldType: new NumberFieldType(),
    input: { value: '123', field: { field: { number_decimal_places: 1 } } },
    output: '123.0',
  },
  {
    fieldType: new NumberFieldType(),
    input: {
      value: 'a string',
      field: { field: { number_decimal_places: 1 } },
    },
    output: new NumberFieldType().getDefaultValue({
      number_decimal_places: 1,
    }),
  },
  {
    fieldType: new NumberFieldType(),
    input: { value: '12.55', field: { field: { number_decimal_places: 1 } } },
    output: '12.6',
  },
  {
    fieldType: new RatingFieldType(),
    input: { value: '3', field: {} },
    output: 3,
  },
  {
    fieldType: new RatingFieldType(),
    input: { value: 7, field: { max_value: 5 } },
    output: 5,
  },
  {
    fieldType: new BooleanFieldType(),
    input: { value: 'true', field: {} },
    output: true,
  },
  {
    fieldType: new BooleanFieldType(),
    input: { value: 'a string', field: {} },
    output: false,
  },
  {
    fieldType: new BooleanFieldType(),
    input: { value: 'false', field: {} },
    output: false,
  },
  {
    fieldType: new DateFieldType(),
    input: { value: '33/12/2021', field: { field: { date_format: 'EU' } } },
    output: null,
  },
  {
    fieldType: new DateFieldType(),
    input: { value: '31/12/2021', field: { field: { date_format: 'EU' } } },
    output: '2021-12-31',
  },
  {
    fieldType: new DateFieldType(),
    input: {
      value: '31/12/2021 22:57',
      field: { field: { date_format: 'EU', date_include_time: true } },
    },
    output: '2021-12-31T22:57:00Z',
  },
  {
    fieldType: new DateFieldType(),
    input: { value: '12/31/2021', field: { field: { date_format: 'US' } } },
    output: '2021-12-31',
  },
  {
    fieldType: new DateFieldType(),
    input: {
      value: '12/31/2021 22:57',
      field: { field: { date_format: 'EU', date_include_time: true } },
    },
    output: '2021-12-31T22:57:00Z',
  },
  {
    fieldType: new DateFieldType(),
    input: { value: '2021-12-31', field: { field: { date_format: 'ISO' } } },
    output: '2021-12-31',
  },
  {
    fieldType: new DateFieldType(),
    input: {
      value: '2021-12-31 22:57',
      field: { field: { date_format: 'ISO', date_include_time: true } },
    },
    output: '2021-12-31T22:57:00Z',
  },
  {
    fieldType: new URLFieldType(),
    input: { value: 'http://www.example.com', field: {} },
    output: 'http://www.example.com',
  },
  {
    fieldType: new EmailFieldType(),
    input: { value: 'test@test.com', field: {} },
    output: 'test@test.com',
  },
  {
    fieldType: new SingleSelectFieldType(),
    input: {
      value: 'test',
      field: { field: { select_options: [{ value: 'test' }] } },
    },
    output: { value: 'test' },
  },
  {
    fieldType: new SingleSelectFieldType(),
    input: {
      value: 'test2',
      field: {
        field: { select_options: [{ value: 'test' }, { value: 'test2' }] },
      },
    },
    output: { value: 'test2' },
  },
  {
    fieldType: new MultipleSelectFieldType(),
    input: {
      value: 'test,test2',
      field: {
        field: {
          select_options: [{ value: 'test' }, { value: 'test2' }],
        },
      },
    },
    output: [{ value: 'test' }, { value: 'test2' }],
  },
  {
    fieldType: new MultipleSelectFieldType(),
    input: {
      value: 'test,nonsense',
      field: {
        field: {
          select_options: [{ value: 'test' }, { value: 'test2' }],
        },
      },
    },
    output: [{ value: 'test' }],
  },
  {
    fieldType: new PhoneNumberFieldType(),
    input: { value: '+1 (123) 456-7890', field: {} },
    output: '+1 (123) 456-7890',
  },
  {
    fieldType: new DurationFieldType(),
    input: { value: '1:01', field: { field: { duration_format: 'h:mm' } } },
    output: 3660,
  },
  {
    fieldType: new DurationFieldType(),
    input: {
      value: '1:01:01',
      field: { field: { duration_format: 'h:mm:ss' } },
    },
    output: 3661,
  },
  {
    fieldType: new DurationFieldType(),
    input: { value: 61, field: { field: { duration_format: 'h:mm' } } },
    output: 60, // the value is rounded according to the duration format
  },
  {
    fieldType: new DurationFieldType(),
    input: {
      value: '-1d 2:30:40',
      field: { field: { duration_format: 'h:mm' } },
    },
    output: -((24 + 2) * 3600 + 31 * 60),
  },
  {
    fieldType: new DurationFieldType(),
    input: { value: '-31m', field: { field: { duration_format: 'd h' } } },
    output: -3600,
  },
]

const queryParametersAsyncForParsing = [
  {
    FieldType: LinkRowFieldType,
    data: [
      { results: [{ value: 'test', id: 1 }] },
      { results: [{ value: 'test2', id: 2 }] },
      { results: [{ value: 'test3,test4', id: 3 }] },
    ],
    input: {
      value: 'test,test2',
      field: {
        field: { id: 20 },
        field_component: DEFAULT_FORM_VIEW_FIELD_COMPONENT_KEY,
      },
    },
    output: [{ id: 1, value: 'test' }],
  },
  {
    FieldType: LinkRowFieldType,
    data: [
      { results: [{ value: 'test', id: 1 }] },
      { results: [{ value: 'test2', id: 2 }] },
      { results: [{ value: 'test3,test4', id: 3 }] },
    ],
    input: {
      value: 'test',
      field: { field: { id: 20 }, field_component: 'multiple' },
    },
    output: [{ id: 1, value: 'test' }],
  },
  {
    FieldType: LinkRowFieldType,
    data: [
      { results: [{ value: 'test', id: 1 }] },
      { results: [{ value: 'test3,test4', id: 3 }] },
    ],
    input: {
      value: 'test,"test3,test4"',
      field: { field: { id: 20 }, field_component: 'multiple' },
    },
    output: [
      { id: 1, value: 'test' },
      { id: 3, value: 'test3,test4' },
    ],
  },
  {
    FieldType: LinkRowFieldType,
    data: [{ results: [{ value: 'some other value', id: 1 }] }],
    input: {
      value: 'test',
      field: { field: { id: 20 }, field_component: 'multiple' },
    },
    output: new LinkRowFieldType().getDefaultValue(),
  },
]

describe('FieldType tests', () => {
  let testApp = null
  let fieldRegistry = null

  beforeAll(() => {
    testApp = new TestApp()
    fieldRegistry = testApp._app.$registry.registry.field

    // Make sure that we have a mockedField for every field type in the registry
    expect(Object.keys(fieldRegistry).sort()).toEqual(
      Object.keys(mockedFields).sort()
    )
  })

  afterEach(() => {
    testApp.afterEach()
  })
  test.each(valuesToCall)(
    'Verify that calling prepareValueForCopy will not throw when value is %s',
    (valueType) => {
      const fields = Object.entries(fieldRegistry)
      for (const [key, value] of fields) {
        const fieldItem = mockedFields[key]
        const t = () => {
          value.prepareValueForCopy(
            fieldItem,
            valueType,
            testApp.store.$registry
          )
        }
        expect(t).not.toThrow(TypeError)
      }
    }
  )

  test.each(datePrepareValueForCopy)(
    'Verify that prepareValueForCopy for DateFieldType returns the expected output',
    (value) => {
      const result = new DateFieldType().prepareValueForCopy(
        value.field,
        value.fieldValue
      )
      expect(result).toBe(value.expectedValue)
    }
  )

  test.each(datePrepareValueForPaste)(
    'Verify that prepareValueForPaste for DateFieldType returns the expected output',
    (value) => {
      const result = new DateFieldType().prepareValueForPaste(
        value.field,
        value.fieldValue
      )
      expect(result).toBe(value.expectedValue)
    }
  )

  test.each(queryParametersForParsing)(
    'Verify that parseQueryParameter returns the expected output for each field type',
    ({ input, output, fieldType }) => {
      expect(
        fieldType.parseQueryParameter(input.field, input.value)
      ).toStrictEqual(output)
    }
  )

  test.each(queryParametersAsyncForParsing)(
    'Verify that parseQueryParameter for async field types returns the correct output',
    async ({ data, input, output, FieldType }) => {
      const fieldType = new FieldType({ app: testApp._app })
      let dataI = 0
      const get = () => {
        const returnValue = { data: data[dataI] }
        dataI++
        return returnValue
      }
      const client = { get }
      const result = await fieldType.parseQueryParameter(
        input.field,
        input.value,
        { client, slug: expect.anything() }
      )
      expect(result).toStrictEqual(output)
    }
  )

  test.each(Object.keys(mockedFields))(
    'Verify that the %s getGroupValueFromRowValue, getRowValueFromGroupValue, and' +
      ' isEqual are compatible.',
    (key) => {
      const field = mockedFields[key]
      const fieldType = fieldRegistry[key]

      // Skip fields that are not compatible with group by because they don't have to
      // match.
      if (!fieldType.getCanGroupByInView(field)) {
        return
      }

      const testingRowData = field.testing_row_data || []
      for (let i = 0; i < testingRowData.length; i++) {
        const rowValue = testingRowData[i]
        expect(fieldType.isEqual(field, rowValue, rowValue)).toBe(true)
        const groupValue = fieldType.getGroupValueFromRowValue(field, rowValue)
        const rowValueFromGroupValue = fieldType.getRowValueFromGroupValue(
          field,
          groupValue
        )
        expect(fieldType.isEqual(field, rowValue, rowValueFromGroupValue)).toBe(
          true
        )
      }
    }
  )
})
