export const AGENT_CAPABILITIES = ['chat', 'approve', 'continue']

export const AGENT_DEFAULT_ROLES = {
  chat: 'EDITOR',
  approve: 'EDITOR',
  continue: 'NOBODY',
}

// What applies without RBAC, whatever the stored rules say.
export const AGENT_UNLICENSED_ROLES = {
  chat: 'EVERYONE',
  approve: 'EVERYONE',
  continue: 'NOBODY',
}

/**
 * @param {Function} t Translates a key.
 * @param {object|null} rules The Agent's rules by capability, null while loading.
 * @returns {object} Per capability, why its rule needs attention.
 */
export function agentRuleProblems(t, rules) {
  const problems = {}
  for (const capability of AGENT_CAPABILITIES) {
    const rule = rules?.[capability]
    if (rule?.role === 'CUSTOM' && !rule.subjects.length) {
      problems[capability] = t('agentPermissions.chooseSubjects', {
        setting: t('agentPermissions.' + capability),
      })
    }
  }
  return problems
}
