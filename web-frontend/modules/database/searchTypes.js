import {
  ApplicationSearchType,
  BaseSearchType,
} from '@baserow/modules/core/search/types/base'
import { tableRouteResetViewIfNeeded } from '@baserow/modules/database/utils/routing'

export class DatabaseSearchType extends ApplicationSearchType {
  constructor(context = {}) {
    super(context)
    this.type = 'database'
    this.name = 'Database'
    this.icon = 'iconoir-db'
    this.priority = 1
  }

  _getApplicationId(result) {
    const id = parseInt(result?.metadata?.database_id || result?.id)
    return isNaN(id) ? null : id
  }

  _getApplicationChildren(application) {
    return application.tables
  }

  _getApplicationPath(application, children) {
    return {
      name: 'database-table',
      params: { databaseId: application.id, tableId: children[0].id },
    }
  }
}

export class DatabaseTableSearchType extends BaseSearchType {
  constructor(context = {}) {
    super(context)
    this.type = 'database_table'
    this.name = 'Tables'
    this.icon = 'iconoir-table'
    this.priority = 2
  }

  _hasRequiredMetadata(result) {
    return !!(
      result.metadata &&
      result.metadata.database_id &&
      result.metadata.table_id
    )
  }

  buildUrl(result, context = null) {
    if (!this._hasRequiredMetadata(result)) {
      return null
    }

    return {
      name: 'database-table',
      params: {
        databaseId: result.metadata.database_id,
        tableId: result.metadata.table_id,
        rowId: null,
      },
    }
  }

  isNavigable(result, context = null) {
    return this._hasRequiredMetadata(result)
  }
}

export class DatabaseFieldSearchType extends BaseSearchType {
  constructor(context = {}) {
    super(context)
    this.type = 'database_field'
    this.name = 'Fields'
    this.icon = 'iconoir-input-field'
    this.priority = 6
  }

  _hasRequiredMetadata(result) {
    return !!(
      result.metadata &&
      result.metadata.database_id &&
      result.metadata.table_id
    )
  }

  buildUrl(result, context = null) {
    if (!this._hasRequiredMetadata(result)) {
      return null
    }

    return {
      name: 'database-table',
      params: {
        databaseId: result.metadata.database_id,
        tableId: result.metadata.table_id,
        rowId: null,
      },
    }
  }

  isNavigable(result, context = null) {
    return this._hasRequiredMetadata(result)
  }
}

export class DatabaseRowSearchType extends BaseSearchType {
  constructor(context = {}) {
    super(context)
    this.type = 'database_row'
    this.name = 'Rows'
    this.icon = 'iconoir-list'
    this.priority = 7
  }

  _hasRequiredMetadata(result) {
    return !!(
      result.metadata &&
      result.metadata.database_id &&
      result.metadata.table_id &&
      result.metadata.row_id
    )
  }

  buildUrl(result, context = null) {
    if (!this._hasRequiredMetadata(result)) {
      return null
    }

    return tableRouteResetViewIfNeeded({
      databaseId: result.metadata.database_id,
      tableId: result.metadata.table_id,
      rowId: result.metadata.row_id,
    })
  }

  isNavigable(result, context = null) {
    return this._hasRequiredMetadata(result)
  }
}
