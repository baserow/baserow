import { TestApp } from '@baserow/test/helpers/testApp'

describe('Database data provider types', () => {
  let testApp = null

  const row = { id: 42, field_1: 'Ada' }
  const fields = [{ id: 1, type: 'text', name: 'Name' }]
  const applicationContext = { row, fields }

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const fieldsProvider = () =>
    testApp.getRegistry().get('databaseDataProvider', 'fields')

  // A URL is resolved through the fields provider only, so without this the
  // clicked row's id cannot reach a button's URL at all.
  test('the fields provider offers the row id alongside the fields', () => {
    const schema = fieldsProvider().getDataSchema(applicationContext)

    expect(Object.keys(schema.properties)).toStrictEqual(['id', 'field_1'])
    expect(schema.properties.id.type).toBe('number')
  })

  test('the fields provider resolves the row id', () => {
    expect(fieldsProvider().getDataChunk(applicationContext, ['id'])).toBe(42)
  })

  test('the fields provider still stringifies a field value', () => {
    expect(fieldsProvider().getDataChunk(applicationContext, ['field_1'])).toBe(
      'Ada'
    )
  })

  test('the row provider keeps offering the row id', () => {
    const provider = testApp.getRegistry().get('databaseDataProvider', 'row')

    expect(
      provider.getDataSchema(applicationContext).properties.id
    ).toBeTruthy()
    expect(provider.getDataChunk(applicationContext, ['id'])).toBe(42)
  })

  const previousProvider = () =>
    testApp.getRegistry().get('databaseDataProvider', 'previous_action')

  const CREATE_ROW = {
    id: 1,
    type: 'local_baserow_create_row',
    service: { table_id: 7 },
  }
  const UPDATE_ROW = {
    id: 2,
    type: 'local_baserow_update_row',
    service: { table_id: 7 },
  }
  const OPEN_URL = {
    id: 3,
    type: 'open_url',
    url: { formula: '', mode: 'raw' },
  }

  const editorContext = (actions, current) => ({
    workflowActions: actions,
    workflowAction: current,
    tableFields: {
      7: [
        { id: 10, name: 'Name', type: 'text', read_only: false },
        { id: 11, name: 'Created on', type: 'created_on', read_only: true },
      ],
    },
  })

  test('the first action is offered no previous actions', () => {
    const context = editorContext([CREATE_ROW, UPDATE_ROW], CREATE_ROW)

    const schema = previousProvider().getDataSchema(context)

    expect(Object.keys(schema.properties)).toStrictEqual([])
  })

  test('a later action is offered the ones before it, and not itself', () => {
    const context = editorContext([CREATE_ROW, UPDATE_ROW, OPEN_URL], OPEN_URL)

    const schema = previousProvider().getDataSchema(context)

    expect(Object.keys(schema.properties)).toStrictEqual(['1', '2'])
  })

  test('an action is never offered one that sits after it', () => {
    const context = editorContext([CREATE_ROW, UPDATE_ROW], UPDATE_ROW)

    const schema = previousProvider().getDataSchema(context)

    expect(Object.keys(schema.properties)).toStrictEqual(['1'])
  })

  test('an unsaved action is described from the target table fields', () => {
    const unsaved = {
      _clientId: 'abc',
      type: 'local_baserow_create_row',
      service: { table_id: 7 },
    }
    const context = editorContext([unsaved, OPEN_URL], OPEN_URL)

    const schema = previousProvider().getDataSchema(context)

    // Keyed by the client id until the action is saved.
    expect(Object.keys(schema.properties)).toStrictEqual(['abc'])
    // A read only field is still readable out of a created row.
    expect(Object.keys(schema.properties.abc.properties)).toStrictEqual([
      'id',
      'field_10',
      'field_11',
    ])
    // Named as the backend names it, so saving the action does not rename
    // the node under the user.
    expect(schema.properties.abc.properties.id.title).toBe(
      'dataProviderTypes.previousActionRowId'
    )
  })

  test('open_url contributes nothing, having no result', () => {
    const context = editorContext([OPEN_URL, CREATE_ROW], CREATE_ROW)

    const schema = previousProvider().getDataSchema(context)

    expect(Object.keys(schema.properties)).toStrictEqual([])
  })

  test('two actions of the same type are told apart', () => {
    const second = { ...CREATE_ROW, id: 4 }
    const context = editorContext([CREATE_ROW, second, OPEN_URL], OPEN_URL)

    const schema = previousProvider().getDataSchema(context)

    expect(schema.properties['1'].title).not.toBe(schema.properties['4'].title)
    expect(schema.properties['4'].title).toMatch(/2$/)
  })

  test('a result is resolved through the field names it came with', () => {
    const context = {
      previousActionResults: {
        1: { data: { id: 99, Name: 'Ada' }, fieldNames: { field_10: 'Name' } },
      },
    }

    expect(previousProvider().getDataChunk(context, ['1', 'id'])).toBe(99)
    expect(previousProvider().getDataChunk(context, ['1', 'field_10'])).toBe(
      'Ada'
    )
  })

  test('an action that produced nothing resolves to null', () => {
    const context = { previousActionResults: {} }

    expect(previousProvider().getDataChunk(context, ['1', 'id'])).toBe(null)
  })
})
