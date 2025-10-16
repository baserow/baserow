import { BaseSearchType } from '@baserow/modules/core/search/types/base'

export class DatabaseSearchType extends BaseSearchType {
  constructor() {
    super()
    this.type = 'database'
    this.name = 'Database'
    this.icon = 'iconoir-db'
    this.priority = 1
  }

  buildUrl(result, context = null) {
    const databaseId = result?.metadata?.database_id || result?.id
    if (!databaseId) {
      return null
    }

    if (context && context.store) {
      const application = context.store.getters['application/get'](databaseId)
      if (application && application.tables && application.tables.length > 0) {
        const tables = application.tables
          .map((t) => t)
          .sort((a, b) => a.order - b.order)

        if (tables.length > 0) {
          return `/database/${databaseId}/table/${tables[0].id}`
        }
      }
    }

    return null
  }
}

export class DatabaseTableSearchType extends BaseSearchType {
  constructor() {
    super()
    this.type = 'database_table'
    this.name = 'Tables'
    this.icon = 'iconoir-table'
    this.priority = 2
  }

  buildUrl(result, context = null) {
    if (
      !result.metadata ||
      !result.metadata.database_id ||
      !result.metadata.table_id
    ) {
      return null
    }

    return `/database/${result.metadata.database_id}/table/${result.metadata.table_id}`
  }
}

export class DatabaseFieldSearchType extends BaseSearchType {
  constructor() {
    super()
    this.type = 'database_field'
    this.name = 'Fields'
    this.icon = 'iconoir-input-field'
    this.priority = 6
  }

  buildUrl(result, context = null) {
    if (
      !result.metadata ||
      !result.metadata.database_id ||
      !result.metadata.table_id
    ) {
      return null
    }

    return `/database/${result.metadata.database_id}/table/${result.metadata.table_id}`
  }
}

export class DatabaseRowSearchType extends BaseSearchType {
  constructor() {
    super()
    this.type = 'database_row'
    this.name = 'Rows'
    this.icon = 'iconoir-list'
    this.priority = 7
  }

  buildUrl(result, context = null) {
    if (
      !result.metadata ||
      !result.metadata.database_id ||
      !result.metadata.table_id ||
      !result.metadata.row_id
    ) {
      return null
    }

    return `/database/${result.metadata.database_id}/table/${result.metadata.table_id}/row/${result.metadata.row_id}`
  }
}
