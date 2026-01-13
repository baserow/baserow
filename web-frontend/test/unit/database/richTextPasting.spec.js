import { MultipleSelectFieldType } from '@baserow/modules/database/fieldTypes'
import papa from '@baserow/modules/core/plugins/papa'

const richTextValuesForPasting = [
  {
    input: {
      clipboardData: 'test,nonsense,test',
      field: {
        select_options: [
          { value: 'test', id: 1 },
          { value: 'test2', id: 2 },
        ],
      },
    },
    output: [{ value: 'test', id: 1 }],
  },
  {
    input: {
      richClipboardData: [{ value: 'test', id: 10 }],
      field: {
        select_options: [
          { value: 'test', id: 1 },
          { value: 'test2', id: 2 },
        ],
      },
    },
    output: [{ value: 'test', id: 1 }],
  },
  {
    input: {
      richClipboardData: [{ value: 'test', id: 2 }],
      field: {
        select_options: [
          { value: 'test', id: 1 },
          { value: 'test2', id: 2 },
        ],
      },
    },
    output: [{ value: 'test2', id: 2 }],
  },
  {
    input: {
      richClipboardData: [{ value: 'random', id: 2 }],
      field: {
        select_options: [
          { value: 'test', id: 1 },
          { value: 'test', id: 2 },
        ],
      },
    },
    output: [{ value: 'test', id: 2 }],
  },
  {
    input: {
      richClipboardData: [
        { value: 'test', id: 2 },
        { value: 'test', id: 50 },
        { value: 'unknown', id: 60 },
      ],
      field: {
        select_options: [
          { value: 'test', id: 1 },
          { value: 'test2', id: 2 },
        ],
      },
    },
    output: [
      { value: 'test2', id: 2 },
      { value: 'test', id: 1 },
    ],
  },
  {
    input: {
      richClipboardData: [
        { value: 'test', id: 2 },
        { value: 'test', id: 2 },
      ],
      field: {
        select_options: [
          { value: 'test', id: 1 },
          { value: 'test2', id: 2 },
        ],
      },
    },
    output: [{ value: 'test2', id: 2 }],
  },
  {
    input: {
      clipboardData: 'test,test2',
      richClipboardData: 'invalid',
      field: {
        select_options: [
          { value: 'test', id: 1 },
          { value: 'test2', id: 2 },
        ],
      },
    },
    output: [
      { value: 'test', id: 1 },
      { value: 'test2', id: 2 },
    ],
  },
  {
    input: {
      clipboardData: 'test,test',
      richClipboardData: 'invalid',
      field: {
        select_options: [
          { value: 'test', id: 1 },
          { value: 'test', id: 2 },
        ],
      },
    },
    output: [
      { value: 'test', id: 1 },
      { value: 'test', id: 2 },
    ],
  },
  {
    input: {
      clipboardData: 'test,test2,test,test3',
      richClipboardData: 'invalid',
      field: {
        select_options: [
          { value: 'test', id: 1 },
          { value: 'test2', id: 10 },
          { value: 'test', id: 3 },
        ],
      },
    },
    output: [
      { value: 'test', id: 1 },
      { value: 'test2', id: 10 },
      { value: 'test', id: 3 },
    ],
  },
]

describe('Rich test pasting tests', () => {
  test.each(richTextValuesForPasting)(
    'Verify that prepareValueForPaste returns the expected output for multi select' +
      ' type: %j',
    ({ input, output }) => {
      const nuxtApp = useNuxtApp()
      expect(
        new MultipleSelectFieldType({ app: nuxtApp }).prepareValueForPaste(
          input.field,
          input.clipboardData,
          input.richClipboardData
        )
      ).toStrictEqual(output)
    }
  )
})
