import GridView from '@baserow/modules/database/components/view/grid/GridView'
import GridViewFreezeHandle from '@baserow/modules/database/components/view/grid/GridViewFreezeHandle'
import GridViewRowDragging from '@baserow/modules/database/components/view/grid/GridViewRowDragging'
import { GRID_VIEW_MULTI_SELECT_AREA } from '@baserow/modules/database/constants'
import { pathKey } from '@baserow/modules/database/utils/gridGroupByRender'

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

  describe('grouped row dragging', () => {
    const groupField = { id: 2, type: 'text' }
    const groupPath = { field_2: 'A' }
    const sectionKey = pathKey(groupPath, [groupField])
    const row = { id: 20 }
    const context = {
      sourceGroupPath: groupPath,
      groupByFields: [groupField],
      groupBySectionRows: new Map([
        [
          sectionKey,
          new Map([
            [0, { id: 10 }],
            [1, row],
            [2, { id: 30 }],
          ]),
        ],
      ]),
      row,
    }

    test.each([1, 2])(
      'treats insertion position %s beside the source row as a no-op',
      (position) => {
        expect(
          GridViewRowDragging.methods.isGroupedTargetNoop.call(context, {
            sectionKey,
            position,
          })
        ).toBe(true)
      }
    )

    test('keeps a cross-group insertion available', () => {
      expect(
        GridViewRowDragging.methods.isGroupedTargetNoop.call(context, {
          sectionKey: pathKey({ field_2: 'B' }, [groupField]),
          position: 1,
        })
      ).toBe(false)
    })

    test('does not dispatch a move when the pointer has no valid target', async () => {
      const dispatch = vi.fn()
      const dragContext = {
        targetAvailable: false,
        cancel: vi.fn(),
        $store: { dispatch },
      }

      await GridViewRowDragging.methods.up.call(dragContext, {
        preventDefault: vi.fn(),
      })

      expect(dragContext.cancel).toHaveBeenCalledOnce()
      expect(dispatch).not.toHaveBeenCalled()
    })

    test('dispatches an explicit cross-group insertion target', async () => {
      const dispatch = vi.fn().mockResolvedValue()
      const before = { id: 30 }
      const targetPath = { field_2: 'B' }
      const targetDisplay = { field_2: { id: 2, value: 'B' } }
      const dragContext = {
        targetAvailable: true,
        isGroupByMode: true,
        cancel: vi.fn(),
        getScrollElement: () => ({ scrollTop: 40 }),
        $store: { dispatch },
        storePrefix: '',
        table: { id: 1 },
        view: { id: 2 },
        allFieldsInTable: [groupField],
        row,
        targetRow: before,
        sourceGroupPath: groupPath,
        groupTarget: { path: targetPath, display: targetDisplay },
      }

      await GridViewRowDragging.methods.up.call(dragContext, {
        preventDefault: vi.fn(),
      })

      expect(dispatch).toHaveBeenCalledWith('view/grid/moveRow', {
        table: dragContext.table,
        grid: dragContext.view,
        fields: dragContext.allFieldsInTable,
        getScrollTop: expect.any(Function),
        row,
        before,
        sourceGroupPath: groupPath,
        targetGroupPath: targetPath,
        targetGroupDisplay: targetDisplay,
      })
    })
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
