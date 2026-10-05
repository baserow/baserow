import { TestApp } from '@baserow/test/helpers/testApp'
import CrudTable from '@baserow/modules/core/components/crudTable/CrudTable'
import CrudTableColumn from '@baserow/modules/core/crudTable/crudTableColumn'
import SimpleField from '@baserow/modules/core/components/crudTable/fields/SimpleField'
import MoreField from '@baserow/modules/core/components/crudTable/fields/MoreField'
import SkeletonBlock from '@baserow/modules/core/components/SkeletonBlock'
import flushPromises from 'flush-promises'
import { h } from 'vue'

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

  function aPage(rows, count = rows.length) {
    return { data: { count, results: rows } }
  }

  async function mountCrudTable(service, props = {}, slots = {}) {
    return await testApp.mount(CrudTable, {
      slots,
      props: {
        service,
        columns: [new CrudTableColumn('name', 'Name', SimpleField)],
        rowIdKey: 'id',
        ...props,
      },
    })
  }

  test('empty tables keep the title, search, action and menus mounted', async () => {
    const crudTable = await mountCrudTable(
      aService(vi.fn().mockResolvedValue(aPage([]))),
      {},
      {
        title: '<span>Members</span>',
        'header-right-side': '<button>Invite member</button>',
        empty: '<p>No members yet</p>',
        menus: '<span data-test="menus">Menu content</span>',
      }
    )
    await flushPromises()

    expect(crudTable.find('h1').text()).toBe('Members')
    expect(crudTable.find('input').exists()).toBe(true)
    expect(crudTable.find('header button').text()).toBe('Invite member')
    expect(crudTable.find('tbody').text()).toBe('No members yet')
    expect(crudTable.find('[data-test="menus"]').exists()).toBe(true)
    expect(crudTable.find('.data-table__footer').exists()).toBe(false)

    await crudTable.find('input').setValue('missing')
    await flushPromises()
    expect(crudTable.find('tbody').text()).toContain('crudTable.noResults')
    expect(crudTable.find('tbody').text()).not.toContain('No members yet')
  })

  test('the title slot receives the count for non-paginated services', async () => {
    const service = {
      options: { isPaginated: false },
      fetch: vi.fn().mockResolvedValue({ data: [{ id: 1, name: 'Row 1' }] }),
    }
    const crudTable = await mountCrudTable(
      service,
      {},
      {
        title: '<template #default="{ count }">{{ count }} members</template>',
      }
    )
    await flushPromises()
    expect(crudTable.find('h1').text()).toBe('1 members')
  })

  test('the row action button emits the existing context payload', async () => {
    const row = { id: 1, name: 'Row 1' }
    const crudTable = await mountCrudTable(
      aService(vi.fn().mockResolvedValue(aPage([row]))),
      {
        columns: [
          new CrudTableColumn('more', '', MoreField, false, false, true),
        ],
      }
    )
    await flushPromises()
    const button = crudTable.find('tbody button')
    expect(button.attributes('aria-label')).toBe('crudTable.rowActions')
    await button.trigger('click')
    expect(crudTable.emitted('row-context')[0][0]).toMatchObject({
      row,
      target: button.element,
    })
  })

  test('the header and the rows are skeletons spanning all columns', async () => {
    let resolveFetch = null
    const fetch = vi.fn().mockReturnValue(
      new Promise((resolve) => {
        resolveFetch = resolve
      })
    )
    const crudTable = await mountCrudTable(aService(fetch), {
      columns: [
        new CrudTableColumn('name', 'Name', SimpleField),
        new CrudTableColumn('more', '', MoreField, false, false, true),
      ],
    })

    const headerCells = crudTable.findAll('thead th')
    expect(headerCells.length).toBe(1)
    expect(headerCells.at(0).attributes('colspan')).toBe('2')
    expect(headerCells.at(0).findAllComponents(SkeletonBlock).length).toBe(1)

    const skeletonRows = crudTable.findAll('tbody tr[aria-hidden="true"]')
    expect(skeletonRows.length).toBe(10)
    const cells = skeletonRows.at(0).findAll('td')
    expect(cells.length).toBe(1)
    expect(cells.at(0).attributes('colspan')).toBe('2')
    expect(skeletonRows.at(0).findAllComponents(SkeletonBlock).length).toBe(1)

    resolveFetch(aPage([{ id: 1, name: 'Row 1' }]))
    await flushPromises()

    expect(crudTable.findAll('tbody tr[aria-hidden="true"]').length).toBe(0)
    expect(crudTable.findAll('thead th').length).toBe(2)
    expect(crudTable.find('thead').text()).toContain('Name')
    expect(crudTable.find('tbody').text()).toContain('Row 1')
  })

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
      .mockResolvedValueOnce(aPage([{ id: 2, name: 'Newer row' }], 200))
    const crudTable = await mountCrudTable(aService(fetch))

    crudTable.vm.setSearch('newer')
    await flushPromises()
    expect(crudTable.find('tbody').text()).toContain('Newer row')

    resolveFirst(aPage([{ id: 1, name: 'Stale row' }], 100))
    await flushPromises()
    expect(crudTable.find('tbody').text()).toContain('Newer row')
    expect(crudTable.find('tbody').text()).not.toContain('Stale row')
    expect(crudTable.emitted('total-count-update')).toEqual([[200]])
  })

  const expandableRows = [
    { key: 'first', name: 'First row' },
    { key: 'second', name: 'Second row' },
  ]
  const expansionSlots = {
    'expanded-row': ({ row, columns }) =>
      h('tr', [
        h('td', { colspan: columns.length }, `Details for ${row.name}`),
      ]),
  }

  test('multiple rows expand independently by row click or disclosure button', async () => {
    const table = await mountCrudTable(
      aService(vi.fn().mockResolvedValue(aPage(expandableRows))),
      { rowIdKey: 'key' },
      expansionSlots
    )
    await flushPromises()
    expect(table.findAll('.data-table__expanded-rows')).toHaveLength(0)
    await table.find('.data-table__row-group tr').trigger('click')
    const firstButton = table.find('button[aria-expanded="true"]')
    const controls = firstButton.attributes('aria-controls')
    expect(table.find(`[id="${controls}"]`).text()).toBe(
      'Details for First row'
    )

    await table.find('button[aria-expanded="false"]').trigger('click')
    expect(table.findAll('.data-table__expanded-rows')).toHaveLength(2)
    expect(
      table.emitted('row-toggle').map(([event]) => event.expanded)
    ).toEqual([true, true])
    await firstButton.trigger('click')
    expect(table.findAll('.data-table__expanded-rows')).toHaveLength(1)
    expect(table.find('.data-table__expanded-rows').text()).toBe(
      'Details for Second row'
    )
  })

  test('expansion is opt-in and can be restricted to eligible rows', async () => {
    const service = aService(vi.fn().mockResolvedValue(aPage(expandableRows)))
    const plain = await mountCrudTable(service, { rowIdKey: 'key' })
    await flushPromises()
    expect(plain.find('button[aria-expanded]').exists()).toBe(false)
    const table = await mountCrudTable(
      service,
      {
        rowIdKey: 'key',
        rowExpandable: (row) => row.key === 'second',
      },
      expansionSlots
    )
    await flushPromises()
    expect(table.findAll('button[aria-expanded]')).toHaveLength(1)
    await table.find('.data-table__row-group tr').trigger('click')
    expect(table.find('.data-table__expanded-rows').exists()).toBe(false)
    await table.find('button[aria-expanded]').trigger('click')
    expect(table.find('.data-table__expanded-rows').text()).toContain(
      'Second row'
    )
  })

  test('interactive cells, nested targets, and context menus do not toggle a row', async () => {
    const targets = [
      h('button', [h('i', { 'data-test': 'nested' })]),
      h('a', 'Link'),
      h('input'),
      h('select'),
      h('textarea'),
      h('label', 'Label'),
      h('span', { role: 'button' }, 'Custom button'),
      h('span', { tabindex: '0' }, 'Focusable control'),
      h('div', { contenteditable: 'true' }, 'Editable'),
      h('span', { 'data-prevent-row-toggle': '' }, 'Custom action'),
    ]
    const Cell = {
      render: () => h('div', { 'data-test': 'controls' }, targets),
    }
    const table = await mountCrudTable(
      aService(vi.fn().mockResolvedValue(aPage([{ id: 1, name: 'Row' }]))),
      { columns: [new CrudTableColumn('name', 'Name', Cell)] },
      expansionSlots
    )
    await flushPromises()
    for (const target of table.findAll(
      '[data-test="controls"] > *, [data-test="nested"]'
    )) {
      await target.trigger('click')
    }
    await table.find('td').trigger('contextmenu')
    expect(table.emitted('row-context')).toHaveLength(1)
    expect(table.emitted('row-toggle')).toBeUndefined()
    expect(table.find('.data-table__expanded-rows').exists()).toBe(false)
    table.element.setAttribute('tabindex', '0')
    await table.find('td').trigger('click')
    expect(table.find('.data-table__expanded-rows').exists()).toBe(true)
  })

  test('the toggle can be placed in another column with custom content', async () => {
    const table = await mountCrudTable(
      aService(
        vi
          .fn()
          .mockResolvedValue(aPage([{ id: 1, name: 'Row', role: 'Editor' }]))
      ),
      {
        expandColumnKey: 'role',
        columns: [
          new CrudTableColumn('name', 'Name', SimpleField),
          new CrudTableColumn('role', 'Role', SimpleField),
        ],
      },
      { ...expansionSlots, 'row-expansion-toggle': '<span>+3</span>' }
    )
    await flushPromises()
    expect(table.find('td:first-child button').exists()).toBe(false)
    const toggle = table.find('td:nth-child(2) button')
    expect(toggle.text()).toBe('+3')
    await toggle.trigger('click')
    expect(toggle.attributes('aria-expanded')).toBe('true')
    expect(
      table.find('.data-table__expanded-rows td').attributes('colspan')
    ).toBe('2')
  })

  test('sorting and refresh retain expansion by rowIdKey, but searching clears it', async () => {
    const fetch = vi
      .fn()
      .mockResolvedValueOnce(aPage(expandableRows))
      .mockResolvedValue(aPage([...expandableRows].reverse()))
    const table = await mountCrudTable(
      aService(fetch),
      {
        rowIdKey: 'key',
        columns: [new CrudTableColumn('name', 'Name', SimpleField, true)],
      },
      {
        ...expansionSlots,
        menus: ({ refresh }) =>
          h('button', { 'data-test': 'refresh', onClick: refresh }, 'Refresh'),
      }
    )
    await flushPromises()
    await table.find('.data-table__expand').trigger('click')
    await table.find('thead button').trigger('click')
    await flushPromises()
    expect(table.find('.data-table__expanded-rows').text()).toBe(
      'Details for First row'
    )
    await table.find('[data-test="refresh"]').trigger('click')
    await flushPromises()
    expect(table.find('.data-table__expanded-rows').text()).toBe(
      'Details for First row'
    )
    await table.find('.data-table__search input').setValue('row')
    await flushPromises()
    expect(table.find('.data-table__expanded-rows').exists()).toBe(false)
  })

  test('pagination and filters clear expansion without remembering previous pages', async () => {
    const table = await mountCrudTable(
      aService(vi.fn().mockResolvedValue(aPage(expandableRows, 200))),
      { rowIdKey: 'key' },
      expansionSlots
    )
    await flushPromises()
    await table.find('.data-table__expand').trigger('click')
    await table.find('.paginator__button:last-child').trigger('click')
    await flushPromises()
    expect(table.find('.data-table__expanded-rows').exists()).toBe(false)
    await table.find('.paginator__button:first-child').trigger('click')
    await flushPromises()
    expect(table.find('.data-table__expanded-rows').exists()).toBe(false)
    await table.find('.data-table__expand').trigger('click')
    await table.setProps({ filters: { role: 'Editor' } })
    await flushPromises()
    expect(table.find('.data-table__expanded-rows').exists()).toBe(false)
  })

  test('an expanded row removed by refresh is not expanded when it reappears', async () => {
    const fetch = vi
      .fn()
      .mockResolvedValueOnce(aPage(expandableRows))
      .mockResolvedValueOnce(aPage([expandableRows[1]]))
      .mockResolvedValueOnce(aPage(expandableRows))
    const table = await mountCrudTable(
      aService(fetch),
      { rowIdKey: 'key' },
      {
        ...expansionSlots,
        menus: ({ refresh }) =>
          h('button', { 'data-test': 'refresh', onClick: refresh }, 'Refresh'),
      }
    )
    await flushPromises()
    await table.find('.data-table__expand').trigger('click')
    await table.find('[data-test="refresh"]').trigger('click')
    await flushPromises()
    expect(fetch).toHaveBeenCalledTimes(2)
    expect(table.find('.data-table__expanded-rows').exists()).toBe(false)
    expect(table.text()).not.toContain('First row')
    await table.find('[data-test="refresh"]').trigger('click')
    await flushPromises()
    expect(table.find('.data-table__expanded-rows').exists()).toBe(false)
  })

  test('custom rows still render inside a tbody with the original slot props', async () => {
    const table = await mountCrudTable(
      aService(vi.fn().mockResolvedValue(aPage([{ id: 1, name: 'Custom' }]))),
      {},
      {
        rows: ({ rows, deleteRow }) =>
          h('tr', [
            h('td', [
              h(
                'button',
                { onClick: () => deleteRow(rows[0].id) },
                rows[0].name
              ),
            ]),
          ]),
      }
    )
    await flushPromises()
    expect(table.find('table > tbody > tr > td > button').text()).toBe('Custom')
    await table.find('tbody button').trigger('click')
    expect(table.find('tbody').text()).toContain('crudTable.empty')
  })

  test('cell updates, deletes and page-specific events still reach the table and caller', async () => {
    const onCustomAction = vi.fn()
    const Cell = {
      props: ['row'],
      emits: ['row-update', 'row-delete', 'custom-action'],
      setup:
        (props, { emit }) =>
        () =>
          h('div', [
            h('span', { 'data-test': 'name' }, props.row.name),
            h(
              'button',
              {
                'data-test': 'edit',
                onClick: () =>
                  emit('row-update', { ...props.row, name: 'Updated' }),
              },
              'Edit'
            ),
            h(
              'button',
              {
                'data-test': 'delete',
                onClick: () => emit('row-delete', props.row.id),
              },
              'Delete'
            ),
            h(
              'button',
              {
                'data-test': 'custom',
                onClick: () => emit('custom-action', props.row.id),
              },
              'Custom'
            ),
          ]),
    }
    const table = await mountCrudTable(
      aService(vi.fn().mockResolvedValue(aPage([{ id: 1, name: 'Original' }]))),
      { columns: [new CrudTableColumn('name', 'Name', Cell)], onCustomAction },
      {
        ...expansionSlots,
        title: '<template #default="{ count }">{{ count }} items</template>',
      }
    )
    await flushPromises()
    await table.find('.data-table__expand').trigger('click')
    await table.find('[data-test="custom"]').trigger('click')
    expect(onCustomAction).toHaveBeenCalledWith(1)
    await table.find('[data-test="edit"]').trigger('click')
    expect(table.find('[data-test="name"]').text()).toBe('Updated')
    expect(table.find('.data-table__expanded-rows').text()).toBe(
      'Details for Updated'
    )
    await table.find('[data-test="delete"]').trigger('click')
    expect(table.find('.data-table__expanded-rows').exists()).toBe(false)
    expect(table.find('h1').text()).toBe('0 items')
  })

  test('deleting the last row on a later page keeps pagination available', async () => {
    const fetch = vi.fn((_url, page) =>
      Promise.resolve(aPage([{ id: page, name: `Page ${page}` }], 101))
    )
    const table = await mountCrudTable(
      aService(fetch),
      {},
      {
        menus: ({ deleteRow }) =>
          h(
            'button',
            { 'data-test': 'delete', onClick: () => deleteRow(2) },
            'Delete'
          ),
      }
    )
    await flushPromises()
    await table.find('.paginator__button:last-child').trigger('click')
    await flushPromises()
    expect(table.find('tbody').text()).toBe('Page 2')
    await table.find('[data-test="delete"]').trigger('click')
    expect(table.find('.data-table__empty').exists()).toBe(true)
    await table.find('.paginator__button:first-child').trigger('click')
    await flushPromises()
    expect(table.find('tbody').text()).toBe('Page 1')
  })
})
