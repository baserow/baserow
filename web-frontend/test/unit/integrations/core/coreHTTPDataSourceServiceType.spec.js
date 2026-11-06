import { CoreHTTPDataSourceServiceType } from '@baserow/modules/integrations/core/serviceTypes'

const app = {
  $i18n: { t: (key) => key },
  $registry: { get: () => ({}) },
}

const make = () => new CoreHTTPDataSourceServiceType({ app })

describe('CoreHTTPDataSourceServiceType', () => {
  test('is the HTTP request entry of the picker', () => {
    const serviceType = make()

    expect(CoreHTTPDataSourceServiceType.getType()).toBe('http_get')
    expect(serviceType.isDataSource).toBe(true)
    expect(serviceType.hiddenInDataSourcePicker).toBe(false)
    expect(serviceType.icon).toBe('iconoir-globe')
    expect(serviceType.group.id).toBe('http')
    expect(serviceType.integrationType).toBeFalsy()
    expect(serviceType.canBeTested).toBe(true)
  })

  test('each data source says whether it returns a list', () => {
    expect(make().returnsList({ returns_list: false })).toBe(false)
    expect(make().returnsList({ returns_list: true })).toBe(true)
    // A data source of a published page without the value, or none at all.
    expect(make().returnsList({})).toBe(false)
    expect(make().returnsList(undefined)).toBe(false)
    expect(make().supportsPagination({ returns_list: true })).toBe(true)
  })

  test('the response of the last test', () => {
    const response = { data: { items: [{ id: 1 }] } }

    expect(
      make().getSampleResponse({ sample_data: { data: response } })
    ).toEqual(response)
    expect(
      make().getSampleResponse({
        returns_list: true,
        sample_data: {
          data: { results: [{ id: 1 }], has_next_page: false, response },
        },
      })
    ).toEqual(response)
    // The JSON body can be null.
    expect(make().getSampleResponse({ sample_data: { data: null } })).toBe(null)
    // Not tested, a failed test, or a list tested before the response was kept.
    expect(make().getSampleResponse({ sample_data: null })).toBeUndefined()
    expect(
      make().getSampleResponse({ sample_data: { _error: 'Nope' } })
    ).toBeUndefined()
    expect(
      make().getSampleResponse({
        returns_list: true,
        sample_data: { data: { results: [], has_next_page: false } },
      })
    ).toBeUndefined()
  })

  test('the schema is the one of the service', () => {
    const schema = { type: 'object', properties: {} }
    expect(make().getDataSchema({ schema })).toBe(schema)
  })

  test('getErrorMessage flags a missing url', () => {
    expect(make().getErrorMessage({ service: { url: { formula: '' } } })).toBe(
      'serviceType.errorUrlMissing'
    )
  })

  test('getErrorMessage asks for a test while there is no schema', () => {
    expect(
      make().getErrorMessage({
        service: { url: { formula: "'https://x'" }, schema: null },
      })
    ).toBe('serviceType.errorHTTPDataSourceNotTested')
  })

  test('getErrorMessage passes once tested', () => {
    expect(
      make().getErrorMessage({
        service: {
          url: { formula: "'https://x'" },
          schema: { type: 'object' },
        },
      })
    ).toBeNull()
  })

  test('getErrorMessage checks nothing when the url is not loaded', () => {
    expect(make().getErrorMessage({ service: {} })).toBeNull()
  })

  test('list records are identified by their id, or else their position', () => {
    const serviceType = make()
    const list = { returns_list: true }

    expect(serviceType.getIdProperty(list, { id: 'abc' })).toBe('id')
    expect(serviceType.getIdProperty(list, { name: 'a', _id: 0 })).toBe('_id')
    // A record with an `id` in a list where others have none has a position
    // too, which is what tells it apart from them.
    expect(serviceType.getIdProperty(list, { id: 'abc', _id: 0 })).toBe('_id')
    expect(serviceType.getRecordName(list, { name: 'Ada', id: 1 })).toBe('Ada')
    expect(serviceType.getRecordName(list, { id: 'abc' })).toBe('abc')
    expect(serviceType.getRecordName(list, { _id: 3 })).toBe(3)
  })

  test('only a list has a result of records', () => {
    const data = { results: [{ id: 1 }] }

    expect(make().getResult({ returns_list: true }, data)).toEqual([{ id: 1 }])
    expect(make().getResult({ returns_list: false }, data)).toBeNull()
  })

  test('list record ids are strings', () => {
    const serviceType = make()

    expect(serviceType.parseRecordId('abc')).toBe('abc')
    expect(serviceType.parseRecordId(4)).toBe('4')
    expect(serviceType.parseRecordId('')).toBeNull()
    expect(serviceType.getRecordIdDataType({})).toBe('string')
    expect(serviceType.getMaxResultLimit({})).toBe(100)
  })
})

describe('CoreHTTPDataSourceServiceType description', () => {
  const describeUrl = (type, url) =>
    useNuxtApp().$registry.get('service', type).getDescription({ type, url })

  test('shows the method and the URL', () => {
    expect(
      describeUrl('http_get', {
        formula: "'https://httpbin.org/get'",
        mode: 'simple',
      })
    ).toBe('GET https://httpbin.org/get')
    expect(
      describeUrl('http_get', {
        formula: "concat('https://api.test/items/', get('page_parameter.id'))",
        mode: 'simple',
      })
    ).toBe('GET https://api.test/items/{page_parameter.id}')
  })

  test('shows an advanced formula as it is written', () => {
    expect(
      describeUrl('http_get', {
        formula: "concat('https://api.test/', 'items')",
        mode: 'advanced',
      })
    ).toBe("GET concat('https://api.test/', 'items')")
  })

  test('shows the type name without a URL', () => {
    expect(describeUrl('http_get', { formula: '', mode: 'simple' })).toBe(
      'serviceType.coreHTTPDataSource'
    )
  })
})

describe('CoreHTTPDataSourceServiceType collection fields', () => {
  test('a table starts with a column per plain value of the records', () => {
    const service = {
      schema: {
        type: 'array',
        items: {
          type: 'object',
          properties: {
            _id: { type: 'integer' },
            name: { type: 'string' },
            price: { type: ['number', 'null'] },
            in_stock: { type: 'boolean' },
            "o'clock": { type: 'string' },
            'a.b': { type: 'string' },
            tags: { type: 'array', items: { type: 'string' } },
            owner: { type: 'object', properties: {} },
          },
        },
      },
    }

    const fields = make().getDefaultCollectionFields(service)

    expect(fields.map(({ id, ...field }) => field)).toEqual([
      {
        name: 'name',
        type: 'text',
        value: { formula: "get('current_record.name')" },
      },
      {
        name: 'price',
        type: 'text',
        value: { formula: "get('current_record.price')" },
      },
      {
        name: 'in_stock',
        type: 'boolean',
        value: { formula: "get('current_record.in_stock')" },
      },
      {
        name: "o'clock",
        type: 'text',
        value: { formula: "get('current_record.o\\'clock')" },
      },
    ])
    expect(new Set(fields.map(({ id }) => id)).size).toBe(4)
  })

  test('a list that was never tested has no columns yet', () => {
    expect(make().getDefaultCollectionFields({ schema: null })).toEqual([])
  })
})
