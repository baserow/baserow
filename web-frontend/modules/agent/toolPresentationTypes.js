import { STEP_STATUS } from '@baserow/modules/core/chatRuns/constants'
import {
  ToolPresentationType,
  WORKSPACE_TOOL_GROUP,
} from '@baserow/modules/core/toolPresentationTypes'

const countIsKnown = (count) => Number.isSafeInteger(count) && count >= 0

/** Database presenters share count/table formatting; Core knows neither field. */
class DatabaseToolPresentationType extends ToolPresentationType {
  static getType() {
    return this.definition.type
  }

  get icon() {
    return 'iconoir-db'
  }

  get group() {
    return this.constructor.definition.read ? WORKSPACE_TOOL_GROUP : null
  }

  get labelKey() {
    return `agent.tool${this.constructor.definition.label}`
  }

  getLabel(t) {
    return t(this.labelKey)
  }

  getDescription(t) {
    return t(`${this.labelKey}Description`)
  }

  getActivity({ status, input, facts }, t) {
    const { counted, table } = this.constructor.definition
    if (status !== STEP_STATUS.RUNNING && status !== STEP_STATUS.DONE) {
      return this.getLabel(t)
    }
    const count =
      status === STEP_STATUS.RUNNING ? input.requested_count : facts.count
    // Requested counts never establish how many records were actually changed.
    if (
      status === STEP_STATUS.DONE &&
      counted === true &&
      !countIsKnown(count)
    ) {
      return this.getLabel(t)
    }
    const hasCount =
      (counted === true || counted === status) && countIsKnown(count)
    const hasTable =
      status === STEP_STATUS.DONE &&
      table &&
      typeof facts.table === 'string' &&
      facts.table.trim()
    const key = `${this.labelKey}${status === STEP_STATUS.RUNNING ? 'Running' : 'Done'}${hasCount ? 'Count' : ''}${hasTable ? 'Table' : ''}`
    return t(
      key,
      {
        ...(hasCount ? { count } : {}),
        ...(hasTable ? { table: facts.table } : {}),
      },
      hasCount ? count : undefined
    )
  }
}

export class ListTablesToolPresentationType extends DatabaseToolPresentationType {
  static definition = { type: 'list_tables', label: 'ListTables', read: true }
}

export class GetTableSchemaToolPresentationType extends DatabaseToolPresentationType {
  static definition = {
    type: 'get_table_schema',
    label: 'GetTableSchema',
    read: true,
    table: true,
    counted: STEP_STATUS.RUNNING,
  }
}

export class ListTableRowsToolPresentationType extends DatabaseToolPresentationType {
  static definition = {
    type: 'list_table_rows',
    label: 'ListTableRows',
    read: true,
    table: true,
    counted: STEP_STATUS.DONE,
  }
}

export class ListViewsToolPresentationType extends DatabaseToolPresentationType {
  static definition = {
    type: 'list_views',
    label: 'ListViews',
    read: true,
    table: true,
  }
}

export class CreateTablesToolPresentationType extends DatabaseToolPresentationType {
  static definition = {
    type: 'create_tables',
    label: 'CreateTables',
    counted: true,
    table: true,
  }
}

export class CreateFieldsToolPresentationType extends DatabaseToolPresentationType {
  static definition = {
    type: 'create_fields',
    label: 'CreateFields',
    counted: true,
    table: true,
  }
}

export class UpdateFieldsToolPresentationType extends DatabaseToolPresentationType {
  static definition = {
    type: 'update_fields',
    label: 'UpdateFields',
    counted: true,
  }
}

export class DeleteFieldsToolPresentationType extends DatabaseToolPresentationType {
  static definition = {
    type: 'delete_fields',
    label: 'DeleteFields',
    counted: true,
  }
}

export class CreateViewsToolPresentationType extends DatabaseToolPresentationType {
  static definition = {
    type: 'create_views',
    label: 'CreateViews',
    counted: true,
    table: true,
  }
}

export class CreateViewFiltersToolPresentationType extends DatabaseToolPresentationType {
  static definition = {
    type: 'create_view_filters',
    label: 'CreateViewFilters',
    counted: true,
  }
}

export class CreateRowsToolPresentationType extends DatabaseToolPresentationType {
  static definition = {
    type: 'create_rows',
    label: 'CreateRows',
    counted: true,
    table: true,
  }
}

export class UpdateRowsToolPresentationType extends DatabaseToolPresentationType {
  static definition = {
    type: 'update_rows',
    label: 'UpdateRows',
    counted: true,
    table: true,
  }
}

export class DeleteRowsToolPresentationType extends DatabaseToolPresentationType {
  static definition = {
    type: 'delete_rows',
    label: 'DeleteRows',
    counted: true,
    table: true,
  }
}

export const agentToolPresentationTypes = [
  ListTablesToolPresentationType,
  GetTableSchemaToolPresentationType,
  ListTableRowsToolPresentationType,
  ListViewsToolPresentationType,
  CreateTablesToolPresentationType,
  CreateFieldsToolPresentationType,
  UpdateFieldsToolPresentationType,
  DeleteFieldsToolPresentationType,
  CreateViewsToolPresentationType,
  CreateViewFiltersToolPresentationType,
  CreateRowsToolPresentationType,
  UpdateRowsToolPresentationType,
  DeleteRowsToolPresentationType,
]
