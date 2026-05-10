export function createKanbanView(
  mock,
  application,
  table,
  {
    viewId = 1,
    filters = [],
    sortings = [],
    groupBys = [],
    decorations = [],
    publicView = false,
    singleSelectFieldId = -1,
  }
) {
  const tableId = table.id
  return {
    id: viewId,
    table_id: tableId,
    name: `mock_kanban_${viewId}`,
    order: 0,
    type: 'kanban',
    table: {
      id: tableId,
      name: table.name,
      order: 1,
      database_id: application.id,
    },
    filter_type: 'AND',
    filters_disabled: false,
    public: publicView,
    row_identifier_type: 'id',
    filters,
    sortings,
    group_bys: groupBys,
    decorations,
    filter_groups: [],
    public_view_has_password: false,
    show_logo: true,
    ownership_type: 'collaborative',
    owned_by_id: 20,
    single_select_field: singleSelectFieldId,
    card_cover_image_field: null,
    slug: 'EzWmKdd6skBdTpyWy_uzJBufXwupO1gM3GFpgb7Ub0s',
    _: {
      type: {
        type: 'kanban',
        iconClass: 'baserow-icon-kanban',
        colorClass: 'color-success',
        name: 'Kanban',
        canFilter: true,
        canSort: true,
        canShare: true,
        canGroupBy: false,
      },
      selected: true,
      loading: false,
      focusFilter: null,
    },
  }
}

export function thereAreRowsInKanbanView(mock, fieldOptions, rows) {
  mock.onGet(/views\/kanban\/.+/).reply(200, {
    field_options: fieldOptions,
    rows_metadata: {},
    rows,
  })
}
