const TOOL_LABELS = {
  list_tables: ['agent.toolListTables', 'agent.toolListTablesDescription'],
  get_table_schema: [
    'agent.toolGetTableSchema',
    'agent.toolGetTableSchemaDescription',
  ],
  list_table_rows: [
    'agent.toolListTableRows',
    'agent.toolListTableRowsDescription',
  ],
  list_views: ['agent.toolListViews', 'agent.toolListViewsDescription'],
  create_tables: [
    'agent.toolCreateTables',
    'agent.toolCreateTablesDescription',
  ],
  create_fields: [
    'agent.toolCreateFields',
    'agent.toolCreateFieldsDescription',
  ],
  update_fields: [
    'agent.toolUpdateFields',
    'agent.toolUpdateFieldsDescription',
  ],
  delete_fields: [
    'agent.toolDeleteFields',
    'agent.toolDeleteFieldsDescription',
  ],
  create_views: ['agent.toolCreateViews', 'agent.toolCreateViewsDescription'],
  create_view_filters: [
    'agent.toolCreateViewFilters',
    'agent.toolCreateViewFiltersDescription',
  ],
  create_rows: ['agent.toolCreateRows', 'agent.toolCreateRowsDescription'],
  update_rows: ['agent.toolUpdateRows', 'agent.toolUpdateRowsDescription'],
  delete_rows: ['agent.toolDeleteRows', 'agent.toolDeleteRowsDescription'],
}

const GROUPS = {
  database: { label: 'agent.toolGroupDatabase', icon: 'iconoir-db' },
}

/**
 * Groups the tools the backend lists in `available_tools`, in their order, with
 * their translated labels. A tool or group without labels here shows its name.
 *
 * @param {Array} availableTools Each tool's name, group and changes_data.
 * @param {Function} t The translation function.
 * @returns {Array} The groups, each with its type, label, icon and tools.
 */
export function groupAgentTools(availableTools, t) {
  const groups = new Map()
  for (const tool of availableTools) {
    if (!groups.has(tool.group)) {
      const group = GROUPS[tool.group]
      groups.set(tool.group, {
        type: tool.group,
        label: group ? t(group.label) : tool.group,
        icon: group?.icon ?? 'iconoir-tools',
        tools: [],
      })
    }
    const [label, description] = TOOL_LABELS[tool.name] ?? []
    groups.get(tool.group).tools.push({
      name: tool.name,
      changesData: tool.changes_data,
      label: label ? t(label) : tool.name,
      description: description ? t(description) : '',
    })
  }
  return [...groups.values()]
}
