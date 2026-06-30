import GridView from '@baserow/modules/database/components/view/grid/GridView'
import GridViewFreezeHandle from '@baserow/modules/database/components/view/grid/GridViewFreezeHandle'
import { GRID_VIEW_MULTI_SELECT_AREA } from '@baserow/modules/database/constants'

describe('GridView component', () => {
  const fields = [
    { id: 1, name: 'Primary', primary: true },
    { id: 2, name: 'Hidden', primary: false },
    { id: 3, name: 'Visible', primary: false },
  ]
  const fieldOptions = {
    1: { order: 0, hidden: true },
    2: { order: 1, hidden: true },
    3: { order: 2, hidden: false },
  }

  test('leftFields includes the primary field when it is hidden', () => {
    const leftFields = GridView.computed.leftFields.call({
      fields,
      fieldOptions,
      frozenColumnCount: 2,
      hasFrozenColumns: true,
    })

    expect(leftFields.map((field) => field.id)).toEqual([1, 3])
  })

  test('rightVisibleFields includes the primary field when frozen columns are disabled', () => {
    const rightVisibleFields = GridView.computed.rightVisibleFields.call({
      rightFields: fields,
      fieldOptions,
    })

    expect(rightVisibleFields.map((field) => field.id)).toEqual([1, 3])
  })

  test('hiddenFields excludes the primary field when it is hidden', () => {
    const hiddenFields = GridView.computed.hiddenFields.call({
      rightFields: fields,
      fieldOptions,
    })

    expect(hiddenFields.map((field) => field.id)).toEqual([2])
  })

  test('freeze handle sortedFields includes the primary field when it is hidden', () => {
    const sortedFields = GridViewFreezeHandle.computed.sortedFields.call({
      fields,
      fieldOptions,
    })

    expect(sortedFields.map((field) => field.id)).toEqual([1, 3])
  })

  // The post-drag click of a multi-select lands on the rows container; that must not
  // cancel the selection. Regression for group-by, whose rows use their own containers.
  const runCancel = (targetClass) => {
    const dispatch = vi.fn()
    const gridViewEl = document.createElement('div')
    const target = document.createElement('div')
    target.className = targetClass
    gridViewEl.appendChild(target)
    GridView.methods.cancelMultiSelectIfActive.call(
      {
        storePrefix: '',
        $refs: { gridView: gridViewEl },
        $store: {
          getters: {
            'view/grid/getSelectionType': GRID_VIEW_MULTI_SELECT_AREA,
            'view/grid/isMultiSelectActive': true,
          },
          dispatch,
        },
      },
      { shiftKey: false, target }
    )
    return dispatch
  }

  test.each([
    'grid-view__rows',
    'grid-view__row',
    'grid-view__group-by-rows',
    'grid-view__group-by-rows-row',
  ])(
    'cancelMultiSelectIfActive keeps the selection for a click on %s',
    (cls) => {
      expect(runCancel(cls)).not.toHaveBeenCalled()
    }
  )

  test('cancelMultiSelectIfActive cancels a click outside the rows', () => {
    expect(runCancel('some-toolbar-element')).toHaveBeenCalledWith(
      'view/grid/clearAndDisableMultiSelect'
    )
  })

  const navFields = [{ id: 1 }, { id: 2 }, { id: 3 }]
  const runSelectNext = ({ field, direction }) => {
    const dispatch = vi.fn()
    GridView.methods.selectNextCell.call(
      {
        storePrefix: '',
        allVisibleFields: navFields,
        fields: navFields,
        $store: { getters: {}, dispatch },
      },
      { row: { id: 10 }, field, direction }
    )
    return dispatch
  }

  test.each([
    ['next', navFields[2]],
    ['previous', navFields[0]],
  ])(
    'selectNextCell keeps the cell selected at the %s boundary',
    (direction, field) => {
      // Regression: arrow/Tab at the first/last field must not unselect the cell.
      expect(runSelectNext({ field, direction })).not.toHaveBeenCalled()
    }
  )

  test('selectNextCell moves to the next field within bounds', () => {
    expect(
      runSelectNext({ field: navFields[0], direction: 'next' })
    ).toHaveBeenCalledWith('view/grid/setSelectedCell', {
      rowId: 10,
      fieldId: 2,
      fields: navFields,
    })
  })

  const groupFields = [
    { id: 1, name: 'Name', type: 'text', primary: true },
    { id: 2, name: 'Team', type: 'text' },
  ]
  const createGroupedAddRowAfterContext = (rows) => {
    const addRow = vi.fn()
    return {
      addRow,
      context: {
        storePrefix: '',
        fields: groupFields,
        activeGroupBys: [{ field: 2 }],
        viewHasGroupBys: true,
        $registry: {
          get: () => ({
            getGroupValueFromRowValue: (_field, value) => value,
          }),
        },
        $store: {
          getters: {
            'view/grid/getAllRows': rows,
          },
        },
        addRow,
        getGroupByFields: GridView.methods.getGroupByFields,
        getGroupPathForRow: GridView.methods.getGroupPathForRow,
        rowsBelongToSameGroup: GridView.methods.rowsBelongToSameGroup,
      },
    }
  }

  test('addRowAfter inserts before the next row when it is in the same group', () => {
    const selectedRow = { id: 1, field_2: 'A' }
    const nextRow = { id: 2, field_2: 'A' }
    const { addRow, context } = createGroupedAddRowAfterContext([
      selectedRow,
      nextRow,
    ])

    GridView.methods.addRowAfter.call(context, selectedRow)

    expect(addRow).toHaveBeenCalledWith(
      { groupPath: { field_2: 'A' }, before: nextRow },
      {}
    )
  })

  test('addRowAfter appends to the selected group before a different group', () => {
    const selectedRow = { id: 1, field_2: 'A' }
    const nextRow = { id: 2, field_2: 'B' }
    const { addRow, context } = createGroupedAddRowAfterContext([
      selectedRow,
      nextRow,
    ])

    GridView.methods.addRowAfter.call(context, selectedRow)

    expect(addRow).toHaveBeenCalledWith(
      { groupPath: { field_2: 'A' }, before: null },
      {}
    )
  })
})
