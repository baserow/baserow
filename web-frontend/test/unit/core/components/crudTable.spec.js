import { TestApp } from '@baserow/test/helpers/testApp'
import CrudTable from '@baserow/modules/core/components/crudTable/CrudTable'
import CrudTableColumn from '@baserow/modules/core/crudTable/crudTableColumn'
import SimpleField from '@baserow/modules/core/components/crudTable/fields/SimpleField'
import flushPromises from 'flush-promises'

// Mock out debounce so we dont have to wait or simulate waiting for the search
// debounce.
vi.mock('lodash/debounce', () => ({ default: vi.fn((fn) => fn) }))

describe('CrudTable component', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => await testApp.afterEach())

  function aService(fetch) {
    return {
      options: { isPaginated: true, baseUrl: '/service/', urlParams: {} },
      fetch,
    }
  }

  function aPage(rows) {
    return { data: { count: rows.length, results: rows } }
  }

  async function mountCrudTable(service, props = {}) {
    return await testApp.mount(CrudTable, {
      props: {
        service,
        columns: [new CrudTableColumn('name', 'Name', SimpleField)],
        rowIdKey: 'id',
        ...props,
      },
    })
  }

  test('the default search is applied to the first fetch and the input', async () => {
    const fetch = vi.fn().mockResolvedValue(aPage([{ id: 1, name: 'Row 1' }]))
    const crudTable = await mountCrudTable(aService(fetch), {
      defaultSearch: 'initial search',
    })
    await flushPromises()

    expect(fetch).toHaveBeenCalledTimes(1)
    expect(fetch.mock.calls[0][2]).toBe('initial search')
    expect(crudTable.find('input').element.value).toBe('initial search')
    expect(crudTable.find('tbody').text()).toContain('Row 1')
  })

  test('setSearch updates the input and fetches with the query', async () => {
    const fetch = vi
      .fn()
      .mockResolvedValueOnce(aPage([{ id: 1, name: 'Row 1' }]))
      .mockResolvedValueOnce(aPage([{ id: 2, name: 'Row 2' }]))
    const crudTable = await mountCrudTable(aService(fetch))
    await flushPromises()

    crudTable.vm.setSearch('42')
    await flushPromises()

    expect(fetch).toHaveBeenCalledTimes(2)
    expect(fetch.mock.calls[1][2]).toBe('42')
    expect(crudTable.find('input').element.value).toBe('42')
    expect(crudTable.find('tbody').text()).toContain('Row 2')
  })

  test('a stale response never overwrites the response of a newer fetch', async () => {
    let resolveFirst = null
    const fetch = vi
      .fn()
      .mockImplementationOnce(
        () => new Promise((resolve) => (resolveFirst = resolve))
      )
      .mockResolvedValueOnce(aPage([{ id: 2, name: 'Newer row' }]))
    const crudTable = await mountCrudTable(aService(fetch))

    crudTable.vm.setSearch('newer')
    await flushPromises()
    expect(crudTable.find('tbody').text()).toContain('Newer row')

    resolveFirst(aPage([{ id: 1, name: 'Stale row' }]))
    await flushPromises()
    expect(crudTable.find('tbody').text()).toContain('Newer row')
    expect(crudTable.find('tbody').text()).not.toContain('Stale row')
  })
})
