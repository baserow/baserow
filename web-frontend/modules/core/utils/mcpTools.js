/**
 * The tools listed under one of the groups, the only ones the user can pick.
 */
export function listedTools(tools, groups) {
  const listed = new Set(groups.map((group) => group.type))
  return tools.filter((tool) => listed.has(tool.group))
}

/**
 * Names of the tools in `grant`, in the order the API listed the tools.
 */
export function grantedToolNames(tools, grant) {
  return tools.map((tool) => tool.name).filter((name) => grant.includes(name))
}

/**
 * Names of the tools the "Read only" preset picks: the read-only tools in a
 * group with `read_only_preset`, in the listed order.
 */
export function readOnlyToolNames(tools, groups) {
  const preset = new Set(
    groups.filter((group) => group.read_only_preset).map((group) => group.type)
  )
  return tools
    .filter((tool) => preset.has(tool.group) && tool.read_only)
    .map((tool) => tool.name)
}
