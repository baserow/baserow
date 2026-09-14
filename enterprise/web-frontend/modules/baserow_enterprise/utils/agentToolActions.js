/**
 * Calls to action for finished tool calls: links to the rows, tables, views,
 * workflows and pages a tool created or changed. Each action is
 * `{ key, label, to }` where `to` is a router location. Locations that need
 * an id the result doesn't carry (e.g. the database of a table) are resolved
 * from the applications in the store.
 */

const ROW_TOOL_RE = /^(create|update|delete)_rows_in_table_(\d+)$/

function findDatabaseForTable(applications, tableId) {
  return applications.find(
    (application) =>
      application.type === 'database' &&
      (application.tables || []).some((table) => table.id === tableId)
  )
}

function tableLocation(applications, tableId) {
  const database = findDatabaseForTable(applications, tableId)
  if (!database) {
    return null
  }
  return {
    name: 'database-table',
    params: { databaseId: database.id, tableId },
  }
}

function rowLocation(applications, tableId, rowId) {
  const database = findDatabaseForTable(applications, tableId)
  if (!database) {
    return null
  }
  return {
    name: 'database-table-row',
    params: { databaseId: database.id, tableId, rowId },
  }
}

function content(result) {
  const value = result?.content
  return value && typeof value === 'object' ? value : {}
}

export function getToolActions({ toolName, args, result, applications, t }) {
  if (!result || result.status !== 'ok') {
    return []
  }
  const actions = []
  const add = (key, label, to) => {
    if (to && !actions.some((action) => action.key === key)) {
      actions.push({ key, label, to })
    }
  }
  const data = content(result)
  const rowMatch = ROW_TOOL_RE.exec(toolName || '')
  if (rowMatch) {
    const tableId = parseInt(rowMatch[2])
    const rowIds =
      rowMatch[1] === 'create'
        ? data.created_row_ids || []
        : rowMatch[1] === 'update'
          ? data.updated_row_ids || []
          : []
    if (rowIds.length === 1) {
      add(
        `row-${tableId}-${rowIds[0]}`,
        t('agentToolActions.viewRow'),
        rowLocation(applications, tableId, rowIds[0])
      )
    } else {
      add(
        `table-${tableId}`,
        t('agentToolActions.openTable'),
        tableLocation(applications, tableId)
      )
    }
    return actions
  }
  switch (toolName) {
    case 'create_tables':
      for (const table of data.created_tables || []) {
        add(
          `table-${table.id}`,
          t('agentToolActions.openNamedTable', { name: table.name }),
          tableLocation(applications, table.id)
        )
      }
      break
    case 'create_fields':
    case 'update_fields':
    case 'delete_fields':
    case 'create_view_filters': {
      const tableId = args?.table_id
      if (tableId) {
        add(
          `table-${tableId}`,
          t('agentToolActions.openTable'),
          tableLocation(applications, tableId)
        )
      }
      break
    }
    case 'create_views': {
      const tableId = args?.table_id
      for (const view of data.created_views || []) {
        const location = tableLocation(applications, tableId)
        if (location) {
          add(
            `view-${view.id}`,
            t('agentToolActions.openNamedView', { name: view.name }),
            {
              ...location,
              params: { ...location.params, viewId: view.id },
            }
          )
        }
      }
      break
    }
    case 'create_workflows': {
      // The result only carries the workflow; its automation is the argument.
      const automationId = args?.automation_id
      for (const workflow of data.created_workflows || []) {
        if (workflow.id && automationId) {
          add(
            `workflow-${workflow.id}`,
            t('agentToolActions.openNamedWorkflow', { name: workflow.name }),
            {
              name: 'automation-workflow',
              params: { automationId, workflowId: workflow.id },
            }
          )
        }
      }
      break
    }
    case 'create_pages': {
      const builderId = args?.application_id
      for (const page of data.created_pages || []) {
        if (page.id && builderId) {
          add(
            `page-${page.id}`,
            t('agentToolActions.openNamedPage', { name: page.name }),
            {
              name: 'builder-page',
              params: { builderId, pageId: page.id },
            }
          )
        }
      }
      break
    }
  }
  return actions
}
