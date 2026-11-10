const GROUPS = {
  database: { label: 'agent.toolGroupDatabase', icon: 'iconoir-db' },
}

/**
 * Groups the tools the backend lists in `available_tools`, in their order, with
 * their translated labels. A group without a label here, or a tool without a
 * registered presenter, shows its name.
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
    const presenter = registry.exists('toolPresentation', tool.name)
      ? registry.get('toolPresentation', tool.name)
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

/**
 * The tools that ask first once the allowed tools change. Allowed tools keep
 * their setting, and change tools that become allowed ask first.
 *
 * @param {Array} availableTools Each tool's name and changes_data.
 * @param {Iterable<string>} prevAllowed The names allowed before the change.
 * @param {Iterable<string>} prevAskFirst The names asking first before it.
 * @param {Iterable<string>} nextAllowed The names allowed after it.
 * @returns {Array<string>} The names that ask first, in `availableTools` order.
 */
export function nextAskFirst(
  availableTools,
  prevAllowed,
  prevAskFirst,
  nextAllowed
) {
  const wasAllowed = new Set(prevAllowed)
  const askedFirst = new Set(prevAskFirst)
  const allowed = new Set(nextAllowed)
  return availableTools
    .filter(
      (tool) =>
        allowed.has(tool.name) &&
        (askedFirst.has(tool.name) ||
          (tool.changes_data && !wasAllowed.has(tool.name)))
    )
    .map((tool) => tool.name)
}
