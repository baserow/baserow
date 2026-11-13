import { TestApp } from '@baserow/test/helpers/testApp'

describe('ServiceType result values', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const serviceType = (type) => testApp.getRegistry().get('service', type)

  const listService = {
    schema: {
      type: 'array',
      items: {
        type: 'object',
        properties: { field_10: { type: 'string', title: 'Name' } },
      },
    },
    sample_data: { data: { results: [{ id: 1, Name: 'Acme' }] } },
  }

  test('reads a value from any result of a list service', () => {
    const type = serviceType('local_baserow_list_rows')
    const result = {
      results: [
        { id: 5, Name: 'Globex' },
        { id: 6, Name: null },
      ],
    }

    expect(type.getResultValue(listService, result, ['0', 'field_10'])).toBe(
      'Globex'
    )
    expect(type.getResultValue(listService, result, ['1', 'field_10'])).toBe(
      null
    )
    expect(
      type.getResultValue(listService, result, ['2', 'field_10'])
    ).toBeUndefined()
    expect(type.getResultValue(listService, null, ['0'])).toBeUndefined()
  })

  test('reads a sample value from the result of the last test', () => {
    const type = serviceType('local_baserow_list_rows')

    expect(type.getSampleValue(listService, ['0', 'field_10'])).toBe('Acme')
    expect(
      type.getSampleValue({ ...listService, sample_data: null }, ['0'])
    ).toBeUndefined()
    expect(
      type.getSampleValue({ ...listService, sample_data: { _error: 'Boom' } }, [
        '0',
      ])
    ).toBeUndefined()
  })
})
