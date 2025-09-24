export function createGalleryView(
  mock,
  application,
  table,
  {
    viewType = 'gallery',
    viewId = 1,
    filters = [],
    sortings = [],
    decorations = [],
  }
) {
  const tableId = table.id
  const galleryView = {
    id: viewId,
    table_id: tableId,
    name: `mock_view_${viewId}`,
    order: 0,
    type: viewType,
    table: {
      id: tableId,
      name: table.name,
      order: 0,
      database_id: application.id,
    },
    filter_type: 'AND',
    filters_disabled: false,
    ownership_type: 'collaborative',
    filters,
    sortings,
    decorations,
  }
  mock.onGet(`/database/views/table/${tableId}/`).reply(200, [galleryView])
  return galleryView
}

export function createGalleryRows(mock, view, fields, rows = []) {
  const fieldOptions = {}
  for (let i = 1; i < fields.length; i++) {
    fieldOptions[i] = {
      hidden: false,
      order: i,
    }
  }
  mock.onGet(`/database/views/gallery/${view.id}/`).reply(200, {
    count: rows.length,
    results: rows,
    field_options: fieldOptions,
  })
}
