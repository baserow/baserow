import { TestApp } from '@baserow/test/helpers/testApp'
import {
  groupPathFromRow,
  placeAbsoluteRowsIntoSections,
} from '@baserow/modules/database/utils/gridGroupBy'
import { pathKey } from '@baserow/modules/database/utils/gridGroupByRender'
import { computeRowMatchFlags } from '@baserow/modules/database/utils/row'
import { getRowSortFunction } from '@baserow/modules/database/utils/view'

const makeRows = () =>
  [
    ['2024-01-08T09:00:01.123Z', 'Charlie'],
    ['2024-01-08T09:00:02.456Z', 'Alpha'],
    ['2024-01-08T09:00:03.789Z', 'Delta'],
    ['2024-01-08T09:00:04.999Z', 'Bravo'],
    ['2024-01-08T09:05:00Z', 'Echo'],
    ['2024-01-08T09:05:00Z', 'Foxtrot'],
  ].map(([date, title], index) => ({
    id: index + 1,
    order: String(index + 1),
    field_1: date,
    field_2: title,
    field_3: '',
  }))

describe.each(['date', 'created_on', 'last_modified'])(
  '%s minute grouping',
  (type) => {
    let testApp
    let registry
    let field

    beforeEach(() => {
      testApp = new TestApp()
      registry = testApp._app.$registry
      field = { id: 1, type, date_include_time: true }
    })

    afterEach(async () => {
      await testApp.afterEach()
    })

    test('places rows with seconds and milliseconds into the backend minute sections', () => {
      const rows = makeRows()
      const backendRows = [rows[1], rows[3], rows[0], rows[2], rows[4], rows[5]]
      const sections = [
        { value: '2024-01-08T09:00:00Z', offset: 0, count: 4 },
        { value: '2024-01-08T09:05:00Z', offset: 4, count: 2 },
      ].map(({ value, offset, count }) => {
        const path = { field_1: value }
        return {
          path,
          sectionKey: pathKey(path, [field]),
          absoluteRowOffset: offset,
          startPosition: 0,
          endPosition: count,
        }
      })

      expect(groupPathFromRow(rows[0], [field], registry)).toEqual({
        field_1: '2024-01-08T09:00:00Z',
      })
      const placements = placeAbsoluteRowsIntoSections({
        absoluteRows: Object.fromEntries(backendRows.map((row, i) => [i, row])),
        sections,
        fields: [field],
        registry,
      })
      expect(placements.map(({ rows }) => rows.map(({ id }) => id))).toEqual([
        [2, 4, 1, 3],
        [5, 6],
      ])
    })

    test.each([
      ['ASC', [7, 2, 4, 1, 3, 5, 6]],
      ['DESC', [5, 6, 2, 4, 1, 3, 7]],
    ])('uses the view sort within a minute when grouping %s', (order, ids) => {
      const rows = [
        ...makeRows(),
        { id: 7, order: '7', field_1: null, field_2: 'Empty', field_3: '' },
      ]
      const fields = [field, { id: 2, type: 'text' }, { id: 3, type: 'text' }]
      const groupBys = [{ field: 1, order, type: 'default' }]
      const view = {
        filters_disabled: true,
        sortings: [{ field: 2, order: 'ASC', type: 'default' }],
      }
      const sorted = [...rows].sort(
        getRowSortFunction(registry, view.sortings, fields, groupBys)
      )
      expect(sorted.map(({ id }) => id)).toEqual(ids)

      // Editing an unrelated field must not show a false "Row has moved" warning.
      for (const row of sorted) {
        expect(
          computeRowMatchFlags({
            row: { ...row, field_3: 'Edited notes' },
            view,
            fields,
            registry,
            rowsInSortingGroup: sorted,
            groupBys,
          })
        ).toEqual({ matchFilters: true, matchSortings: true })
      }
    })

    test('uses canonical UTC minutes regardless of the display timezone', () => {
      const fieldType = registry.get('field', type)
      expect(
        fieldType.getGroupValueFromRowValue(
          { ...field, date_force_timezone: 'Asia/Kathmandu' },
          '2024-01-08T10:00:04.123+01:00'
        )
      ).toBe('2024-01-08T09:00:00Z')
      expect(fieldType.getGroupValueFromRowValue(field, null)).toBeNull()
    })

    test('keeps ordinary date sorting precise to milliseconds', () => {
      const fieldType = registry.get('field', type)
      const earlier = { field_1: '2024-01-08T09:00:01.123Z' }
      const later = { field_1: '2024-01-08T09:00:01.456Z' }
      expect(fieldType.getSort('field_1', 'ASC')(earlier, later)).toBeLessThan(
        0
      )
      expect(
        fieldType.getSort('field_1', 'DESC')(earlier, later)
      ).toBeGreaterThan(0)
      expect(
        fieldType.getGroupBySort(
          'field_1',
          'ASC',
          field,
          'default'
        )(earlier, later)
      ).toBe(0)
    })

    test('preserves date-only group values', () => {
      expect(
        registry
          .get('field', type)
          .getGroupValueFromRowValue(
            { ...field, date_include_time: false },
            '2024-01-08'
          )
      ).toBe('2024-01-08')
    })
  }
)

describe('derived date fields', () => {
  let testApp

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  test('preserves full timestamp groups and ordering for date formulas', () => {
    const registry = testApp._app.$registry
    const field = {
      id: 1,
      type: 'formula',
      formula_type: 'date',
      date_include_time: true,
    }
    const rows = makeRows().slice(0, 4)
    expect(groupPathFromRow(rows[0], [field], registry)).toEqual({
      field_1: '2024-01-08T09:00:01.123Z',
    })
    expect(
      [...rows]
        .sort(
          getRowSortFunction(
            registry,
            [{ field: 2, order: 'ASC', type: 'default' }],
            [field, { id: 2, type: 'text' }],
            [{ field: 1, order: 'ASC', type: 'default' }]
          )
        )
        .map(({ id }) => id)
    ).toEqual([1, 2, 3, 4])
  })

  test('preserves timestamp values in date lookup arrays', () => {
    const field = {
      type: 'lookup',
      formula_type: 'array',
      array_formula_type: 'date',
      date_include_time: true,
    }
    const value = [{ id: 1, value: '2024-01-08T09:00:01.123Z' }]
    expect(
      testApp._app.$registry
        .get('field', 'lookup')
        .getGroupValueFromRowValue(field, value)
    ).toEqual(value)
  })
})

describe('optimistic audit dates', () => {
  let testApp

  beforeEach(() => {
    testApp = new TestApp()
    vi.useFakeTimers({ toFake: ['Date'] })
    vi.setSystemTime(new Date('2024-01-08T23:30:45.123Z'))
  })

  afterEach(async () => {
    vi.useRealTimers()
    await testApp.afterEach()
  })

  test.each([
    ['created_on', false, '2024-01-08'],
    ['created_on', true, '2024-01-08T23:30:45Z'],
    ['last_modified', false, '2024-01-08'],
    ['last_modified', true, '2024-01-08T23:30:45Z'],
  ])('%s new rows respect include time %s', (type, includeTime, expected) => {
    const field = {
      id: 1,
      type,
      date_include_time: includeTime,
      date_force_timezone: 'Asia/Kathmandu',
    }
    const fieldType = testApp._app.$registry.get('field', type)
    expect(fieldType.getNewRowValue(field)).toBe(expected)
  })

  test.each([
    [false, '2024-01-08'],
    [true, '2024-01-08T23:30:45Z'],
  ])(
    'last modified edits and moves respect include time %s',
    (includeTime, expected) => {
      const field = {
        id: 1,
        type: 'last_modified',
        date_include_time: includeTime,
      }
      const fieldType = testApp._app.$registry.get('field', 'last_modified')
      expect(fieldType.onRowChange({}, field, '2024-01-07')).toBe(expected)
      expect(fieldType.onRowMove({}, '2', '1', field, '2024-01-07')).toBe(
        expected
      )
    }
  )

  test('same-day edits retain date-only grouping and ordinary date sorting', () => {
    const registry = testApp._app.$registry
    const field = { id: 1, type: 'last_modified', date_include_time: false }
    const fields = [field, { id: 2, type: 'text' }]
    const rows = [
      { id: 1, order: '1', field_1: '2024-01-08', field_2: '' },
      { id: 2, order: '2', field_1: '2024-01-08', field_2: '' },
    ]
    const fieldType = registry.get('field', 'last_modified')
    const editedRow = {
      ...rows[0],
      field_1: fieldType.onRowChange(rows[0], field, rows[0].field_1),
      field_2: 'Edited notes',
    }
    expect(groupPathFromRow(editedRow, [field], registry)).toEqual({
      field_1: '2024-01-08',
    })
    for (const order of ['ASC', 'DESC']) {
      expect(fieldType.getSort('field_1', order)(editedRow, rows[1])).toBe(0)
      expect(
        computeRowMatchFlags({
          row: editedRow,
          view: {
            filters_disabled: true,
            sortings: [{ field: 1, order, type: 'default' }],
          },
          fields,
          registry,
          rowsInSortingGroup: rows,
          groupBys: [{ field: 1, order: 'ASC', type: 'default' }],
        })
      ).toEqual({ matchFilters: true, matchSortings: true })
    }
  })
})
