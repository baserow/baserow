import { STEP_STATUS } from '@baserow/modules/core/chatRuns/constants'
import {
  ToolPresentationType,
  WORKSPACE_TOOL_GROUP,
} from '@baserow/modules/core/toolPresentationTypes'

const countIsKnown = (count) => Number.isSafeInteger(count) && count >= 0

/** The table a call's request names, or '' when it names none. */
const requestedTable = (input) =>
  typeof input?.values?.table === 'string' ? input.values.table.trim() : ''

/** Database presenters share count/table formatting; Core knows neither field. */
class DatabaseToolPresentationType extends ToolPresentationType {
  static getType() {
    return this.definition.type
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

  getInput({ input }) {
    return this.constructor.definition.read ? null : input
  }

  /** A held call hasn't run, so it is titled by what it asks to do. */
  getHeldActivity({ input }, t) {
    const count = input.requested_count
    if (this.constructor.definition.counted !== true || !countIsKnown(count)) {
      return this.getLabel(t)
    }
    const table = this.constructor.definition.table ? requestedTable(input) : ''
    return table
      ? t(`${this.labelKey}HeldCountTable`, { count, table }, count)
      : t(`${this.labelKey}HeldCount`, { count }, count)
  }

  getActivity({ status, input, facts }, t) {
    const { counted, table } = this.constructor.definition
    if (status === STEP_STATUS.WAITING || status === STEP_STATUS.REJECTED) {
      return this.getHeldActivity({ input }, t)
    }
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
    // Facts name tables that were created or read; other calls name the table asked for.
    const tableName =
      (typeof facts.table === 'string' && facts.table.trim()) ||
      requestedTable(input)
    const hasTable = status === STEP_STATUS.DONE && table && tableName
    const key = `${this.labelKey}${status === STEP_STATUS.RUNNING ? 'Running' : 'Done'}${hasCount ? 'Count' : ''}${hasTable ? 'Table' : ''}`
    return t(
      key,
      {
        ...(hasCount ? { count } : {}),
        ...(hasTable ? { table: tableName } : {}),
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

/** A search the AI provider runs itself, so it has no tool to allow or configure. */
export class WebSearchToolPresentationType extends ToolPresentationType {
  static getType() {
    return 'web_search'
  }

  getLabel(t) {
    return t('agent.toolWebSearch')
  }

  getQueries({ input }) {
    if (!Array.isArray(input?.queries)) return []
    return input.queries
      .filter((query) => typeof query === 'string')
      .map((query) => query.trim())
      .filter(Boolean)
  }

  getUrl({ input }) {
    return typeof input?.url === 'string' ? input.url.trim() : ''
  }

  getTarget({ input }) {
    return this.getQueries({ input }).join(', ') || this.getUrl({ input })
  }

  getActivity({ status, input }, t) {
    if (input?.unavailable === true) return t('agent.toolWebSearchUnavailable')
    // A step without queries but with a page is the provider opening that page.
    const key =
      this.getQueries({ input }).length === 0 && this.getUrl({ input })
        ? 'agent.toolWebSearchOpenPage'
        : 'agent.toolWebSearch'
    const activity =
      status === STEP_STATUS.RUNNING
        ? t(`${key}Running`)
        : status === STEP_STATUS.DONE
          ? t(`${key}Done`)
          : t(key)
    const target = this.getTarget({ input })
    return target
      ? t('agent.toolWebSearchTarget', { activity, target })
      : activity
  }
}

export const agentToolPresentationTypes = [
  WebSearchToolPresentationType,
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
