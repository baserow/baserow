import { clone } from '@baserow/modules/core/utils/object'
import { anyFieldsNeedFetch } from '@baserow/modules/database/store/field'
import { generateHash } from '@baserow/modules/core/utils/hashing'

/**
 * Registers the real time events related to the database module. When a message comes
 * in, the state of the stores will be updated to match the latest update. In some
 * cases some other events like refreshing all the data needs to be triggered.
 */
export const registerRealtimeEvents = (realtime) => {
  realtime.registerEvent('table_created', ({ store }, data) => {
    const database = store.getters['application/get'](data.table.database_id)
    if (database !== undefined) {
      store.dispatch('table/forceUpsert', { database, data: data.table })
    }
  })

  realtime.registerEvent('table_updated', ({ store, app }, data) => {
    const database = store.getters['application/get'](data.table.database_id)
    if (database !== undefined) {
      const table = database.tables.find((table) => table.id === data.table.id)
      if (table !== undefined) {
        store.dispatch('table/forceUpdate', {
          database,
          table,
          values: data.table,
        })
        if (data.force_table_refresh) {
          app.$bus.$emit('table-refresh', {
            tableId: data.table.id,
          })
        }
      }
    }
  })

  realtime.registerEvent('tables_reordered', ({ store, app }, data) => {
    const database = store.getters['application/getAll'].find(
      (application) => generateHash(application.id) === data.database_id
    )
    if (database !== undefined) {
      store.commit('table/ORDER_TABLES', {
        database,
        order: data.order,
        isHashed: true,
      })
    }
  })

  realtime.registerEvent('table_deleted', ({ store }, data) => {
    const database = store.getters['application/get'](data.database_id)
    if (database !== undefined) {
      const table = database.tables.find((table) => table.id === data.table_id)
      if (table !== undefined) {
        store.dispatch('table/forceDelete', { database, table })
      }
    }
  })

  realtime.registerEvent('field_created', ({ store, app }, data) => {
    const table = store.getters['table/getSelected']
    const registry = app.$registry
    const fieldType = registry.get('field', data.field.type)
    if (table !== undefined && table.id === data.field.table_id) {
      const relatedFields = data.related_fields
      const callback = async () => {
        await store.dispatch('field/forceCreate', {
          table,
          values: data.field,
          relatedFields,
        })
      }
      const view = store.getters['view/getSelected']
      const viewMustBeRefreshed =
        view &&
        app.$registry
          .get('view', view.type)
          .shouldRefreshWhenFieldCreated(
            app.$registry,
            store,
            data.field,
            'page/'
          )
      if (
        fieldType.shouldFetchDataWhenAdded() ||
        anyFieldsNeedFetch(relatedFields, registry) ||
        viewMustBeRefreshed
      ) {
        app.$bus.$emit('table-refresh', {
          tableId: store.getters['table/getSelectedId'],
          newField: data.field,
          includeFieldOptions: true,
          callback,
        })
      } else {
        callback()
      }
    }
  })

  realtime.registerEvent('field_restored', async ({ store, app }, data) => {
    const table = store.getters['table/getSelected']
    if (table !== undefined && table.id === data.field.table_id) {
      // Trigger a table refresh to get the row data for the field including field
      // options to get those also.
      await store.dispatch('field/forceUpdateFields', {
        fields: data.related_fields,
      })
      app.$bus.$emit('table-refresh', {
        tableId: store.getters['table/getSelectedId'],
        includeFieldOptions: true,
        async callback() {
          await store.dispatch('field/fieldRestored', {
            table,
            selectedView: store.getters['view/getSelected'],
            values: data.field,
          })
        },
      })
    }
  })

  realtime.registerEvent('field_updated', ({ store, app }, data) => {
    const field = store.getters['field/get'](data.field.id)
    if (field !== undefined) {
      const oldField = clone(field)
      // We want to wait for the table to reload before actually updating the field
      // in order to prevent incompatible values for the field.
      const callback = async () => {
        await store.dispatch('field/forceUpdate', {
          field,
          oldField,
          data: data.field,
          relatedFields: data.related_fields,
        })
      }
      if (store.getters['table/getSelectedId'] === data.field.table_id) {
        app.$bus.$emit('table-refresh', {
          callback,
          tableId: store.getters['table/getSelectedId'],
          sourceEvent: {
            type: 'field_updated',
            data,
          },
        })
      } else {
        // If the current page is not the table we don't have to wait for the
        // refresh so we can update the field right away.
        callback()
      }
    }
  })

  realtime.registerEvent('field_deleted', async ({ store, app }, data) => {
    const field = store.getters['field/get'](data.field_id)
    if (field !== undefined) {
      await store.dispatch('field/forceDelete', field)
      if (store.getters['table/getSelectedId'] === data.table_id) {
        await store.dispatch('field/forceUpdateFields', {
          fields: data.related_fields,
        })
        app.$bus.$emit('table-refresh', {
          tableId: store.getters['table/getSelectedId'],
          sourceEvent: {
            type: 'field_deleted',
            data,
          },
        })
      }
    }
  })

  realtime.registerEvent('rows_created', (context, data) => {
    const { app, store } = context
    for (const viewType of Object.values(app.$registry.getAll('view'))) {
      for (let i = 0; i < data.rows.length; i++) {
        const row = data.rows[i]

        viewType.rowCreated(
          context,
          data.table_id,
          store.getters['field/getAll'],
          data.rows[i],
          data.metadata[row.id],
          'page/'
        )
      }
    }
  })

  realtime.registerEvent('rows_updated', async (context, data) => {
    const { app, store } = context
    for (const viewType of Object.values(app.$registry.getAll('view'))) {
      for (let i = 0; i < data.rows.length; i++) {
        const row = data.rows[i]

        // A row may be updated by the backend, while it wasn't requested by the user,
        // causing rows before update and rows updated sets asymmetry. In that case,
        // we just want a skeleton of a row.
        const rowBeforeUpdate = data.rows_before_update[i] || { id: row.id }

        await viewType.rowUpdated(
          context,
          data.table_id,
          store.getters['field/getAll'],
          rowBeforeUpdate,
          row,
          data.metadata[row.id],
          data.updated_field_ids,
          'page/'
        )
      }
    }
    for (let i = 0; i < data.rows.length; i++) {
      store.dispatch('rowModal/updated', {
        tableId: data.table_id,
        values: data.rows[i],
      })
    }
  })

  realtime.registerEvent(
    'rows_ai_values_generation_error',
    async (context, data) => {
      const { app } = context

      for (const viewType of Object.values(app.$registry.getAll('view'))) {
        await viewType.AIValuesGenerationError(
          context,
          data.table_id,
          data.field_id,
          data.row_ids,
          data.error,
          'page/'
        )
      }
    }
  )

  realtime.registerEvent('rows_deleted', (context, data) => {
    const { app, store } = context
    for (const viewType of Object.values(app.$registry.getAll('view'))) {
      for (let i = 0; i < data.rows.length; i++) {
        const row = data.rows[i]
        viewType.rowDeleted(
          context,
          data.table_id,
          store.getters['field/getAll'],
          row,
          'page/'
        )
      }
    }
  })

  realtime.registerEvent('row_orders_recalculated', ({ store, app }, data) => {
    if (store.getters['table/getSelectedId'] === data.table_id) {
      app.$bus.$emit('table-refresh', {
        tableId: store.getters['table/getSelectedId'],
      })
    }
  })

  realtime.registerEvent('row_history_updated', ({ store }, data) => {
    const rowHistoryEntry = data.row_history_entry
    store.dispatch('rowHistory/forceCreate', {
      rowHistoryEntry,
      rowId: data.row_id,
      tableId: data.table_id,
    })
  })

  realtime.registerEvent('view_created', ({ store }, data) => {
    if (store.getters['table/getSelectedId'] === data.view.table_id) {
      store.dispatch('view/forceCreate', { data: data.view })
    }
  })

  realtime.registerEvent('view_updated', (context, data) => {
    const { store, app } = context
    const view = store.getters['view/get'](data.view.id)
    if (view !== undefined) {
      const oldView = clone(view)
      store.dispatch('view/forceUpdate', {
        view,
        values: data.view,
        repopulate: true,
      })

      if (view.id === store.getters['view/getSelectedId']) {
        const viewType = app.$registry.get('view', view.type)
        const refresh = viewType.updated(context, view, oldView, 'page/')
        if (
          refresh ||
          view.filter_type !== oldView.filter_type ||
          view.filters_disabled !== oldView.filters_disabled
        ) {
          app.$bus.$emit('table-refresh', {
            tableId: store.getters['table/getSelectedId'],
          })
        }
      }
    }
  })

  realtime.registerEvent('views_reordered', ({ store, app }, data) => {
    const table = store.getters['table/getSelected']
    if (table !== undefined && table.id === data.table_id) {
      store.commit('view/ORDER_ITEMS', { order: data.order })
    }
  })

  realtime.registerEvent('view_deleted', ({ store }, data) => {
    const view = store.getters['view/get'](data.view_id)
    if (view !== undefined) {
      store.dispatch('view/forceDelete', view)
    }
  })

  realtime.registerEvent('force_view_rows_refresh', ({ store, app }, data) => {
    const view = store.getters['view/get'](data.view_id)
    if (view !== undefined) {
      if (store.getters['view/getSelectedId'] === view.id) {
        app.$bus.$emit('table-refresh', {
          tableId: store.getters['table/getSelectedId'],
        })
      }
    }
  })

  realtime.registerEvent('force_view_refresh', async ({ store, app }, data) => {
    const view = store.getters['view/get'](data.view_id)
    if (view !== undefined) {
      if (store.getters['view/getSelectedId'] === view.id) {
        const updateViewPromise = store.dispatch('view/forceUpdate', {
          view,
          values: data.view,
          repopulate: true,
        })
        const updateFieldsPromise = store.dispatch('field/forceSetFields', {
          fields: data.fields,
        })

        // This makes sure both dispatches are executed in parallel.
        await Promise.all([updateViewPromise, updateFieldsPromise])

        app.$bus.$emit('table-refresh', {
          tableId: store.getters['table/getSelectedId'],
          includeFieldOptions: true,
        })
      }
    }
  })

  realtime.registerEvent('view_filter_created', ({ store, app }, data) => {
    const view = store.getters['view/get'](data.view_filter.view)
    if (view !== undefined) {
      store.dispatch('view/forceCreateFilter', {
        view,
        values: data.view_filter,
      })
      if (store.getters['view/getSelectedId'] === view.id) {
        app.$bus.$emit('table-refresh', {
          tableId: store.getters['table/getSelectedId'],
        })
      }
    }
  })

  realtime.registerEvent('view_filter_updated', ({ store, app }, data) => {
    const view = store.getters['view/get'](data.view_filter.view)
    if (view !== undefined) {
      const filter = view.filters.find(
        (filter) => filter.id === data.view_filter.id
      )
      if (filter !== undefined) {
        store.dispatch('view/forceUpdateFilter', {
          filter,
          values: data.view_filter,
        })
        if (store.getters['view/getSelectedId'] === view.id) {
          app.$bus.$emit('table-refresh', {
            tableId: store.getters['table/getSelectedId'],
          })
        }
      }
    }
  })

  realtime.registerEvent('view_filter_deleted', ({ store, app }, data) => {
    const view = store.getters['view/get'](data.view_id)
    if (view !== undefined) {
      const filter = view.filters.find(
        (filter) => filter.id === data.view_filter_id
      )
      if (filter !== undefined) {
        store.dispatch('view/forceDeleteFilter', { view, filter })
        if (store.getters['view/getSelectedId'] === view.id) {
          app.$bus.$emit('table-refresh', {
            tableId: store.getters['table/getSelectedId'],
          })
        }
      }
    }
  })

  realtime.registerEvent(
    'view_filter_group_created',
    ({ store, app }, data) => {
      const view = store.getters['view/get'](data.view_filter_group.view)
      if (view !== undefined) {
        store.dispatch('view/forceCreateFilterGroup', {
          view,
          values: data.view_filter_group,
        })
        if (store.getters['view/getSelectedId'] === view.id) {
          app.$bus.$emit('table-refresh', {
            tableId: store.getters['table/getSelectedId'],
          })
        }
      }
    }
  )

  realtime.registerEvent(
    'view_filter_group_updated',
    ({ store, app }, data) => {
      const view = store.getters['view/get'](data.view_filter_group.view)
      if (view !== undefined) {
        const filterGroup = view.filter_groups.find(
          (group) => group.id === data.view_filter_group.id
        )
        if (filterGroup !== undefined) {
          store.dispatch('view/forceUpdateFilterGroup', {
            filterGroup,
            values: data.view_filter_group,
          })
          if (store.getters['view/getSelectedId'] === view.id) {
            app.$bus.$emit('table-refresh', {
              tableId: store.getters['table/getSelectedId'],
            })
          }
        }
      }
    }
  )

  realtime.registerEvent(
    'view_filter_group_deleted',
    ({ store, app }, data) => {
      const view = store.getters['view/get'](data.view_id)
      if (view !== undefined) {
        const filterGroup = view.filter_groups.find(
          (group) => group.id === data.view_filter_group_id
        )
        if (filterGroup !== undefined) {
          store.dispatch('view/forceDeleteFilterGroup', {
            view,
            filterGroup,
          })
          if (store.getters['view/getSelectedId'] === view.id) {
            app.$bus.$emit('table-refresh', {
              tableId: store.getters['table/getSelectedId'],
            })
          }
        }
      }
    }
  )

  realtime.registerEvent('view_sort_created', ({ store, app }, data) => {
    const view = store.getters['view/get'](data.view_sort.view)
    if (view !== undefined) {
      store.dispatch('view/forceCreateSort', {
        view,
        values: data.view_sort,
      })
      if (store.getters['view/getSelectedId'] === view.id) {
        app.$bus.$emit('table-refresh', {
          tableId: store.getters['table/getSelectedId'],
        })
      }
    }
  })

  realtime.registerEvent('view_sort_updated', ({ store, app }, data) => {
    const view = store.getters['view/get'](data.view_sort.view)
    if (view !== undefined) {
      const sort = view.sortings.find((sort) => sort.id === data.view_sort_id)
      if (sort !== undefined) {
        store.dispatch('view/forceUpdateSort', {
          sort,
          values: data.view_sort,
        })
        if (store.getters['view/getSelectedId'] === view.id) {
          app.$bus.$emit('table-refresh', {
            tableId: store.getters['table/getSelectedId'],
          })
        }
      }
    }
  })

  realtime.registerEvent('view_sort_deleted', ({ store, app }, data) => {
    const view = store.getters['view/get'](data.view_id)
    if (view !== undefined) {
      const sort = view.sortings.find((sort) => sort.id === data.view_sort_id)
      if (sort !== undefined) {
        store.dispatch('view/forceDeleteSort', { view, sort })
        if (store.getters['view/getSelectedId'] === view.id) {
          app.$bus.$emit('table-refresh', {
            tableId: store.getters['table/getSelectedId'],
          })
        }
      }
    }
  })

  realtime.registerEvent('view_group_by_created', ({ store, app }, data) => {
    const view = store.getters['view/get'](data.view_group_by.view)
    if (view !== undefined) {
      store.dispatch('view/forceCreateGroupBy', {
        view,
        values: data.view_group_by,
      })
      if (store.getters['view/getSelectedId'] === view.id) {
        app.$bus.$emit('table-refresh', {
          tableId: store.getters['table/getSelectedId'],
        })
      }
    }
  })

  realtime.registerEvent('view_group_by_updated', ({ store, app }, data) => {
    const view = store.getters['view/get'](data.view_group_by.view)
    if (view !== undefined) {
      const groupBy = view.group_bys.find(
        (groupBy) => groupBy.id === data.view_group_by_id
      )
      if (groupBy !== undefined) {
        store.dispatch('view/forceUpdateGroupBy', {
          groupBy,
          values: data.view_group_by,
        })
        if (store.getters['view/getSelectedId'] === view.id) {
          app.$bus.$emit('table-refresh', {
            tableId: store.getters['table/getSelectedId'],
          })
        }
      }
    }
  })

  realtime.registerEvent('view_group_by_deleted', ({ store, app }, data) => {
    const view = store.getters['view/get'](data.view_id)
    if (view !== undefined) {
      const groupBy = view.group_bys.find(
        (groupBy) => groupBy.id === data.view_group_by_id
      )
      if (groupBy !== undefined) {
        store.dispatch('view/forceDeleteGroupBy', { view, groupBy })
        if (store.getters['view/getSelectedId'] === view.id) {
          app.$bus.$emit('table-refresh', {
            tableId: store.getters['table/getSelectedId'],
          })
        }
      }
    }
  })

  realtime.registerEvent('view_decoration_created', ({ store, app }, data) => {
    const view = store.getters['view/get'](data.view_decoration.view)
    if (view !== undefined) {
      store.dispatch('view/forceCreateDecoration', {
        view,
        values: data.view_decoration,
      })
    }
  })

  realtime.registerEvent('view_decoration_updated', ({ store, app }, data) => {
    const view = store.getters['view/get'](data.view_decoration.view)
    if (view !== undefined) {
      const decoration = view.decorations.find(
        (deco) => deco.id === data.view_decoration_id
      )
      if (decoration !== undefined) {
        store.dispatch('view/forceUpdateDecoration', {
          decoration,
          values: data.view_decoration,
        })
      }
    }
  })

  realtime.registerEvent('view_decoration_deleted', ({ store, app }, data) => {
    const view = store.getters['view/get'](data.view_id)
    if (view !== undefined) {
      const decoration = view.decorations.find(
        (deco) => deco.id === data.view_decoration_id
      )
      if (decoration !== undefined) {
        store.dispatch('view/forceDeleteDecoration', { view, decoration })
      }
    }
  })

  realtime.registerEvent('view_field_options_updated', (context, data) => {
    const { store, app } = context
    const view = store.getters['view/get'](data.view_id)
    if (view !== undefined && view.id === store.getters['view/getSelectedId']) {
      const viewType = app.$registry.get('view', view.type)
      viewType.fieldOptionsUpdated(context, view, data.field_options, 'page/')
    }
  })

  realtime.registerEvent('user_permanently_deleted', ({ store, app }, data) => {
    app.$bus.$emit('table-refresh', {
      tableId: store.getters['table/getSelectedId'],
    })
  })

  realtime.registerEvent('field_rule_added', ({ store, app }, data) => {
    store.commit('fieldRules/ADD_RULE', {
      tableId: data.rule.table_id,
      rule: data.rule,
    })
  })

  realtime.registerEvent('field_rule_updated', ({ store, app }, data) => {
    store.dispatch('fieldRules/ruleChanged', {
      tableId: data.rule.table_id,
      ruleId: data.rule.id,
      rule: data.rule,
    })
  })

  realtime.registerEvent('field_rule_deleted', ({ store, app }, data) => {
    store.commit('fieldRules/DELETE_RULE', {
      tableId: data.rule.table_id,
      ruleId: data.rule.id,
    })
  })
}
