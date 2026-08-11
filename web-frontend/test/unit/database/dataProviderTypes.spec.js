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
})
