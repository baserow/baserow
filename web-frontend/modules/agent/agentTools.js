const GROUPS = {
  database: { label: 'agent.toolGroupDatabase', icon: 'iconoir-db' },
}

/**
 * Groups the tools the backend lists in `available_tools`, in their order, with
 * their translated labels. A tool or group without labels here shows its name.
 *
 * @param {Array} availableTools Each tool's name, group and changes_data.
 * @param {Object} registry The registry containing shared tool presentations.
 * @param {Function} t The translation function.
 * @returns {Array} The groups, each with its type, label, icon and tools.
 */
export function groupAgentTools(availableTools, registry, t) {
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
    const type = tool.presentation_type ?? tool.name
    const presenter = registry.exists('toolPresentation', type)
      ? registry.get('toolPresentation', type)
      : null
    groups.get(tool.group).tools.push({
      name: tool.name,
      changesData: tool.changes_data,
      label: presenter ? presenter.getLabel(t) : tool.name,
      description: presenter ? presenter.getDescription(t) : '',
    })
  }
  return [...groups.values()]
}
