import GridView from '@baserow/modules/database/components/view/grid/GridView'
import GridViewFreezeHandle from '@baserow/modules/database/components/view/grid/GridViewFreezeHandle'
import GridViewGroupByRows from '@baserow/modules/database/components/view/grid/GridViewGroupByRows'
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

  test('group-by banner separators include left row-details and field boundaries', () => {
    const separatorPositions =
      GridViewGroupByRows.computed.bannerSeparatorPositions.call({
        includeRowDetails: true,
        gridViewRowDetailsWidth: 72,
        visibleFields: [
          { id: 1, name: 'Name' },
          { id: 2, name: 'Team' },
          { id: 3, name: 'Notes' },
        ],
        getFieldWidth: (field) => ({ 1: 200, 2: 150, 3: 100 })[field.id],
      })

    expect(separatorPositions).toEqual([72, 272, 422])
  })

  test('group-by banner separators in the right section stay on field boundaries', () => {
    const separatorPositions =
      GridViewGroupByRows.computed.bannerSeparatorPositions.call({
        includeRowDetails: false,
        visibleFields: [
          { id: 1, name: 'Team' },
          { id: 2, name: 'Notes' },
          { id: 3, name: 'Score' },
        ],
        getFieldWidth: (field) => ({ 1: 200, 2: 150, 3: 100 })[field.id],
      })

    expect(separatorPositions).toEqual([200, 350])
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
        scrollToGroupByRowIfNeeded: vi.fn(),
        _emitPresenceCellFocus: vi.fn(),
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
  describe('presence focus after the row edit modal closes', () => {
    const makeContext = ({ cellSelected }) => ({
      presenceFocus: {
        reemitLastFocus: vi.fn(),
        clearFocus: vi.fn(),
      },
      selectedCellComponents: cellSelected ? [{}] : [],
      $emit: vi.fn(),
      _restorePresenceFocusAfterRowModal:
        GridView.methods._restorePresenceFocusAfterRowModal,
    })

    test('rowEditModalHidden re-emits the cell focus when a cell is still selected', () => {
      const ctx = makeContext({ cellSelected: true })

      GridView.methods.rowEditModalHidden.call(ctx, { row: undefined })

      expect(ctx.presenceFocus.reemitLastFocus).toHaveBeenCalledOnce()
      expect(ctx.presenceFocus.clearFocus).not.toHaveBeenCalled()
    })

    test('rowEditModalHidden clears the transmitted focus when no cell is selected', () => {
      const ctx = makeContext({ cellSelected: false })

      GridView.methods.rowEditModalHidden.call(ctx, { row: undefined })

      expect(ctx.presenceFocus.clearFocus).toHaveBeenCalledOnce()
      expect(ctx.presenceFocus.reemitLastFocus).not.toHaveBeenCalled()
    })

    test('route-driven close clears the grid focus when no cell is selected', () => {
      const ctx = makeContext({ cellSelected: false })
      ctx.$refs = {
        rowEditModal: { clearPresenceFocus: vi.fn(), hide: vi.fn() },
        left: { $refs: { body: { scrollTop: 0 } } },
      }
      ctx.$store = { dispatch: vi.fn() }
      ctx.storePrefix = ''
      ctx.view = {}
      ctx.fields = []

      GridView.watch.row.handler.call(ctx, null, { id: 1 })

      expect(ctx.$refs.rowEditModal.clearPresenceFocus).toHaveBeenCalledOnce()
      expect(ctx.presenceFocus.clearFocus).toHaveBeenCalledOnce()
      expect(ctx.presenceFocus.reemitLastFocus).not.toHaveBeenCalled()
      expect(ctx.$refs.rowEditModal.hide).toHaveBeenCalledWith(false)
    })

    test('route-driven close re-emits the cell focus when a cell is selected', () => {
      const ctx = makeContext({ cellSelected: true })
      ctx.$refs = {
        rowEditModal: { clearPresenceFocus: vi.fn(), hide: vi.fn() },
        left: { $refs: { body: { scrollTop: 0 } } },
      }
      ctx.$store = { dispatch: vi.fn() }
      ctx.storePrefix = ''
      ctx.view = {}
      ctx.fields = []

      GridView.watch.row.handler.call(ctx, null, { id: 1 })

      expect(ctx.presenceFocus.reemitLastFocus).toHaveBeenCalledOnce()
      expect(ctx.presenceFocus.clearFocus).not.toHaveBeenCalled()
    })
  })
})
