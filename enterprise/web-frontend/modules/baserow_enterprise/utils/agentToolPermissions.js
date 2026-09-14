/**
 * Pure helpers for the workspace tool permissions: the config shape is
 * `{ access, require_write_approval, tool_rules }` (see the backend
 * `tools/rules.py`) and `catalog` is the list returned by the workspace
 * tools endpoint: `[{ name, group, group_label, label, description,
 * is_write }, ...]`.
 */

export const ACCESS_EVERYTHING = 'everything'
export const ACCESS_READ_ONLY = 'read_only'
export const ACCESS_CUSTOM = 'custom'

export const RULE_ALLOW = 'allow'
export const RULE_ASK = 'ask'
export const RULE_OFF = 'off'

export const PRESET_EVERYTHING = 'everything'
export const PRESET_ASK_FIRST = 'ask_first'
export const PRESET_READ_ONLY = 'read_only'
export const PRESET_OFF = 'off'
export const PRESET_CUSTOM = 'custom'

export function normalizeWorkspaceConfig(config) {
  const access = [ACCESS_EVERYTHING, ACCESS_READ_ONLY, ACCESS_CUSTOM].includes(
    config?.access
  )
    ? config.access
    : config?.mode === 'read_only'
      ? ACCESS_READ_ONLY
      : ACCESS_EVERYTHING
  return {
    access,
    require_write_approval: config?.require_write_approval !== false,
    tool_rules: { ...(config?.tool_rules || {}) },
  }
}

function defaultRule(tool, access, requireWriteApproval) {
  if (!tool.is_write) {
    return RULE_ALLOW
  }
  if (access === ACCESS_READ_ONLY) {
    return RULE_OFF
  }
  return requireWriteApproval ? RULE_ASK : RULE_ALLOW
}

/**
 * The effective rule of every catalog tool for the config, mirroring the
 * backend resolver (reads never ask).
 */
export function effectiveRules(config, catalog) {
  const normalized = normalizeWorkspaceConfig(config)
  const rules = {}
  for (const tool of catalog) {
    let rule =
      normalized.access === ACCESS_CUSTOM
        ? normalized.tool_rules[tool.name]
        : undefined
    if (rule === undefined) {
      rule = defaultRule(
        tool,
        normalized.access,
        normalized.require_write_approval
      )
    }
    if (rule === RULE_ASK && !tool.is_write) {
      rule = RULE_ALLOW
    }
    rules[tool.name] = rule
  }
  return rules
}

/**
 * Which preset the rules of a group of tools correspond to, or `custom`.
 */
export function deriveGroupPreset(rules, groupTools) {
  const matches = (expected) =>
    groupTools.every((tool) => rules[tool.name] === expected(tool))
  if (groupTools.length === 0) {
    return PRESET_EVERYTHING
  }
  if (matches(() => RULE_OFF)) {
    return PRESET_OFF
  }
  if (matches(() => RULE_ALLOW)) {
    return PRESET_EVERYTHING
  }
  if (matches((tool) => (tool.is_write ? RULE_ASK : RULE_ALLOW))) {
    return PRESET_ASK_FIRST
  }
  if (matches((tool) => (tool.is_write ? RULE_OFF : RULE_ALLOW))) {
    return PRESET_READ_ONLY
  }
  return PRESET_CUSTOM
}

/**
 * Returns new rules with the preset applied to the given tools.
 */
export function applyGroupPreset(rules, groupTools, preset) {
  const updated = { ...rules }
  for (const tool of groupTools) {
    if (preset === PRESET_OFF) {
      updated[tool.name] = RULE_OFF
    } else if (preset === PRESET_EVERYTHING) {
      updated[tool.name] = RULE_ALLOW
    } else if (preset === PRESET_ASK_FIRST) {
      updated[tool.name] = tool.is_write ? RULE_ASK : RULE_ALLOW
    } else if (preset === PRESET_READ_ONLY) {
      updated[tool.name] = tool.is_write ? RULE_OFF : RULE_ALLOW
    }
  }
  return updated
}

/**
 * Counts for the "{n} tools, {m} ask first" summaries.
 */
export function summarizeAccess(config, catalog) {
  const rules = effectiveRules(config, catalog)
  const values = Object.values(rules)
  return {
    total: catalog.length,
    enabled: values.filter((rule) => rule !== RULE_OFF).length,
    ask: values.filter((rule) => rule === RULE_ASK).length,
  }
}

/**
 * The config to save for edited rules. The top-level access stays when the
 * rules still equal its defaults, so the segment control keeps showing the
 * preset the user picked; otherwise the config becomes custom.
 */
export function buildPermissionsPayload(config, rules, catalog) {
  const normalized = normalizeWorkspaceConfig(config)
  const presets = [ACCESS_EVERYTHING, ACCESS_READ_ONLY]
  for (const access of presets) {
    const candidate = { ...normalized, access, tool_rules: {} }
    const defaults = effectiveRules(candidate, catalog)
    if (catalog.every((tool) => defaults[tool.name] === rules[tool.name])) {
      return candidate
    }
  }
  return { ...normalized, access: ACCESS_CUSTOM, tool_rules: { ...rules } }
}
