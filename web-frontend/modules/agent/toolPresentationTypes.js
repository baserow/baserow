import { STEP_STATUS } from '@baserow/modules/core/chatRuns/constants'
import {
  ToolPresentationType,
  WORKSPACE_TOOL_GROUP,
} from '@baserow/modules/core/toolPresentationTypes'

const countIsKnown = (count) => Number.isSafeInteger(count) && count >= 0
const trimmedName = (name) => (typeof name === 'string' ? name.trim() : '')

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
    return input
  }

  /** Titled by what the call asks to do: counted changes by count, reads by table. */
  getRequestedActivity({ input }, t) {
    const { counted, table: titledByTable } = this.constructor.definition
    const table = titledByTable ? requestedTable(input) : ''
    if (counted !== true) {
      return table
        ? t(`${this.labelKey}RequestedTable`, { table })
        : this.getLabel(t)
    }
    const count = input.requested_count
    if (!countIsKnown(count)) return this.getLabel(t)
    return table
      ? t(`${this.labelKey}RequestedCountTable`, { count, table }, count)
      : t(`${this.labelKey}RequestedCount`, { count }, count)
  }

  getActivity({ status, input, facts }, t) {
    const { counted, table } = this.constructor.definition
    if (status !== STEP_STATUS.RUNNING && status !== STEP_STATUS.DONE) {
      return this.getRequestedActivity({ input }, t)
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

export class ListDatabasesToolPresentationType extends DatabaseToolPresentationType {
  static definition = {
    type: 'list_databases',
    label: 'ListDatabases',
    read: true,
  }
}

/** Database creation and renaming show the requested or confirmed name. */
class DatabaseApplicationToolPresentationType extends DatabaseToolPresentationType {
  getRequestedDatabase(input) {
    return trimmedName(
      input?.values?.[this.constructor.definition.targetNameKey]
    )
  }

  getRequestedActivity({ input }, t) {
    const database = this.getRequestedDatabase(input)
    return database
      ? t(`${this.labelKey}RequestedDatabase`, { database })
      : this.getLabel(t)
  }

  getActivity({ status, input, facts }, t) {
    if (status !== STEP_STATUS.RUNNING && status !== STEP_STATUS.DONE) {
      return this.getRequestedActivity({ input }, t)
    }
    let database = this.getRequestedDatabase(input)
    let activity = 'Running'
    if (status === STEP_STATUS.DONE) {
      database = trimmedName(facts.database)
      activity = facts.changed === false ? 'Unchanged' : 'Done'
    }
    return t(`${this.labelKey}${activity}${database ? 'Database' : ''}`, {
      database,
    })
  }
}

export class CreateDatabaseToolPresentationType extends DatabaseApplicationToolPresentationType {
  static definition = {
    type: 'create_database',
    label: 'CreateDatabase',
    targetNameKey: 'name',
  }
}

export class UpdateDatabaseToolPresentationType extends DatabaseApplicationToolPresentationType {
  static definition = {
    type: 'update_database',
    label: 'UpdateDatabase',
    targetNameKey: 'database',
  }

  getRequestedActivity({ input }, t) {
    const database = this.getRequestedDatabase(input)
    // Stored previews from earlier replies used `name` for the proposed name.
    const newName = trimmedName(input?.values?.new_name ?? input?.values?.name)
    if (database && newName) {
      return t('agent.toolUpdateDatabaseRequestedRename', {
        database,
        newName,
      })
    }
    return super.getRequestedActivity({ input }, t)
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

const MCP_TOOL_NAME = /^mcp\d+_/
const text = (value) =>
  typeof value === 'string' && value.trim() ? value.trim() : null

/**
 * Calls to the tools of an MCP server. Their names are made at runtime from the
 * server's id, so this type claims them by prefix. The server's name and the
 * tool's reviewed title name the call; its arguments are only shown for a call
 * waiting for approval, credentials masked by the backend.
 */
export class MCPServerToolPresentationType extends ToolPresentationType {
  static getType() {
    return 'mcp_server_tool'
  }

  matchesTool(name) {
    return MCP_TOOL_NAME.test(name)
  }

  getLabel(t) {
    return t('agent.toolMCP')
  }

  getInput({ input }) {
    return input?.values ? input : null
  }

  getActivity({ status, input }, t) {
    const tool = text(input.tool)
    const server = text(input.server)
    if (!tool || !server) return this.getLabel(t)
    const key =
      status === STEP_STATUS.RUNNING
        ? 'agent.toolMCPRunning'
        : status === STEP_STATUS.DONE
          ? 'agent.toolMCPDone'
          : 'agent.toolMCPNamed'
    return t(key, { tool, server })
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
  ListDatabasesToolPresentationType,
  ListTablesToolPresentationType,
  GetTableSchemaToolPresentationType,
  ListTableRowsToolPresentationType,
  ListViewsToolPresentationType,
  CreateDatabaseToolPresentationType,
  UpdateDatabaseToolPresentationType,
  CreateTablesToolPresentationType,
  CreateFieldsToolPresentationType,
  UpdateFieldsToolPresentationType,
  DeleteFieldsToolPresentationType,
  CreateViewsToolPresentationType,
  CreateViewFiltersToolPresentationType,
  CreateRowsToolPresentationType,
  UpdateRowsToolPresentationType,
  DeleteRowsToolPresentationType,
  MCPServerToolPresentationType,
]
