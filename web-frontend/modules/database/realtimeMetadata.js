import { isApplicationBundleLoaded } from '@baserow/modules/core/utils/applicationBundles'
import { generateHash } from '@baserow/modules/core/utils/hashing'
import { populateTable } from '@baserow/modules/database/utils/populateTable'

/** Keep unopened databases' table lists current without loading their view stores. */
export default function register(app) {
  const { $realtime: realtime, $store: store } = app
  const update = (database, tables) =>
    store.commit('application/UPDATE_ITEM', {
      id: database.id,
      values: { tables },
      viaRealtime: true,
    })
  for (const event of ['table_created', 'table_updated', 'table_deleted']) {
    realtime.registerEvent(event, (_, data) => {
      if (isApplicationBundleLoaded(app, 'database')) return
      const database = store.getters['application/get'](
        data.table?.database_id ?? data.database_id
      )
      if (!database) return
      const id = data.table?.id ?? data.table_id
      const tables = database.tables.filter((table) => table.id !== id)
      if (event !== 'table_deleted') {
        const previous = database.tables.find((table) => table.id === id)
        tables.push(
          previous ? { ...previous, ...data.table } : populateTable(data.table)
        )
      }
      update(database, tables)
    })
  }
  realtime.registerEvent('tables_reordered', (_, data) => {
    if (isApplicationBundleLoaded(app, 'database')) return
    const database = store.getters['application/getAll'].find(
      (item) => generateHash(item.id) === data.database_id
    )
    if (!database) return
    update(
      database,
      database.tables.map((table) => {
        const index = data.order.indexOf(generateHash(table.id))
        return { ...table, order: index === -1 ? 0 : index + 1 }
      })
    )
  })
}
