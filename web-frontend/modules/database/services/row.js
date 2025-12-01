import _ from 'lodash'
import { callGrouper } from '@baserow/modules/core/utils/function'
import { getUndoRedoActionRequestConfig } from '@baserow/modules/database/utils/action'

const GRACE_DELAY = 50 // ms before querying the backend with a get query

const groupGetNameCalls = callGrouper(GRACE_DELAY)

export default (client) => {
  return {
    get(tableId, rowId, includeMetadata = true, viewId = null) {
      const searchParams = {}
      if (includeMetadata) {
        searchParams.include = 'metadata'
      }
      if (viewId !== null) {
        searchParams.view_id = viewId
      }
      const params = new URLSearchParams(searchParams).toString()
      return client.get(`/database/rows/table/${tableId}/${rowId}/?${params}`)
    },
    fetchAll({
      tableId,
      page = 1,
      size = 10,
      search = null,
      viewId = null,
      searchMode = null,
    }) {
      const config = {
        params: {
          page,
          size,
        },
      }

      if (search !== null && search !== '') {
        config.params.search = search
        config.params.search_mode = searchMode
      }

      if (viewId !== null) {
        config.params.view_id = viewId
      }

      return client.get(`/database/rows/table/${tableId}/`, config)
    },
    /**
     * Returns the name of specified table row. Batch consecutive queries into one
     * during the defined GRACE_TIME.
     */
    getName: groupGetNameCalls(async (argList) => {
      // [[tableId, id], ...] -> { table__<id>: Array<row ids> }
      const tableMap = argList.reduce((acc, [tableId, rowId]) => {
        if (!acc[`table__${tableId}`]) {
          acc[`table__${tableId}`] = new Set()
        }
        acc[`table__${tableId}`].add(rowId)
        return acc
      }, {})

      const config = {
        params: _.mapValues(tableMap, (rowIds) => Array.from(rowIds).join(',')),
      }

      const { data } = await client.get(`/database/rows/names/`, config)

      return (tableId, rowId) => {
        if (!data[tableId]) {
          return null
        }
        return data[tableId][rowId]
      }
    }),
    getIds(tableId, rowNames) {
      return Promise.all(rowNames.map((name) => this.getId(tableId, name)))
    },
    create(tableId, values, beforeId = null, viewId = null) {
      const config = { params: {} }

      if (beforeId !== null) {
        config.params.before = beforeId
      }

      if (viewId !== null) {
        config.params.view = viewId
      }

      return client.post(`/database/rows/table/${tableId}/`, values, config)
    },
    batchCreate(
      tableId,
      rows,
      beforeId = null,
      undoRedoActionGroupId = null,
      viewId = null
    ) {
      const config = getUndoRedoActionRequestConfig({ undoRedoActionGroupId })
      config.params = { include_metadata: true }

      if (beforeId !== null) {
        config.params.before = beforeId
      }

      if (viewId !== null) {
        config.params.view = viewId
      }

      return client.post(
        `/database/rows/table/${tableId}/batch/`,
        { items: rows },
        config
      )
    },
    update(tableId, rowId, values, viewId = null) {
      const config = { params: {} }

      if (viewId !== null) {
        config.params.view = viewId
      }

      return client.patch(
        `/database/rows/table/${tableId}/${rowId}/`,
        values,
        config
      )
    },
    batchUpdate(tableId, items, undoRedoActionGroupId = null, viewId = null) {
      const config = getUndoRedoActionRequestConfig({ undoRedoActionGroupId })
      config.params.include_metadata = true

      if (viewId !== null) {
        config.params.view = viewId
      }

      return client.patch(
        `/database/rows/table/${tableId}/batch/`,
        { items },
        config
      )
    },
    /**
     * Moves the row to the position before the row related to the beforeRowId
     * parameters. If the before id is not provided then the row will be moved
     * to the end.
     */
    move(tableId, rowId, beforeRowId = null) {
      const config = { params: {} }

      if (beforeRowId !== null) {
        config.params.before_id = beforeRowId
      }

      return client.patch(
        `/database/rows/table/${tableId}/${rowId}/move/`,
        null,
        config
      )
    },
    delete(tableId, rowId, viewId) {
      const config = { params: {} }

      if (viewId !== null) {
        config.params.view = viewId
      }

      return client.delete(`/database/rows/table/${tableId}/${rowId}/`, config)
    },
    batchDelete(tableId, items, viewId = null) {
      const config = { params: {} }

      if (viewId !== null) {
        config.params.view = viewId
      }

      return client.post(
        `/database/rows/table/${tableId}/batch-delete/`,
        {
          items,
        },
        config
      )
    },
    getAdjacent({
      tableId,
      rowId,
      viewId = null,
      previous = false,
      search = null,
      searchMode = null,
    }) {
      const searchSanitized = search === '' ? null : search
      return client.get(`/database/rows/table/${tableId}/${rowId}/adjacent/`, {
        params: {
          previous,
          search: searchSanitized,
          view_id: viewId,
          search_mode: searchMode,
        },
      })
    },
  }
}
