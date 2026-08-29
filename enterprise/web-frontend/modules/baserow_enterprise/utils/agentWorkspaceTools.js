/**
 * Pure helpers shared by the workspace tools modal and its tests. `tools` is
 * always the full universe returned by the workspace tools endpoint:
 * `[{ name, group, is_write }, ...]`.
 */

/**
 * The tool names that should start checked in the modal for the given
 * workspace tool config. An explicit `enabled_tools` list wins (unknown names
 * are dropped so stale config entries can't produce phantom selections);
 * otherwise the mode decides: read only preselects the read tools, read +
 * write preselects everything.
 */
export function getInitialWorkspaceToolSelection(config, tools) {
  const enabledTools = config?.enabled_tools
  if (Array.isArray(enabledTools)) {
    const known = new Set(tools.map((tool) => tool.name))
    return enabledTools.filter((name) => known.has(name))
  }
  if (config?.mode === 'read_only') {
    return tools.filter((tool) => !tool.is_write).map((tool) => tool.name)
  }
  return tools.map((tool) => tool.name)
}

/**
 * The config values to PATCH for a selection. A full selection is saved as
 * `enabled_tools: null` so tools added in future Baserow versions are enabled
 * automatically; anything else is saved as the explicit list. The mode is
 * derived from the selection so the read/write preset buttons stay visually
 * consistent with what is actually enabled.
 */
export function buildWorkspaceToolsSavePayload(selectedNames, tools) {
  const selected = new Set(selectedNames)
  const allSelected = tools.every((tool) => selected.has(tool.name))
  const anyWriteSelected = tools.some(
    (tool) => tool.is_write && selected.has(tool.name)
  )
  return {
    enabled_tools: allSelected
      ? null
      : tools.filter((tool) => selected.has(tool.name)).map((t) => t.name),
    mode: anyWriteSelected ? 'read_write' : 'read_only',
  }
}
