import { toFormulaStringLiteral } from '@baserow/modules/core/formula'

export const DESTINATION_TYPE = { CHANNEL: 'channel', CHAT: 'chat' }

// The ids each destination type sends to.
export const DESTINATION_ID_FIELDS = {
  [DESTINATION_TYPE.CHANNEL]: ['team_id', 'channel_id'],
  [DESTINATION_TYPE.CHAT]: ['chat_id'],
}

const STRING_LITERAL = /^\s*'((?:[^'\\]|\\.)*)'\s*$/

/**
 * The id a formula holds, when it's only a string literal, like the ones the
 * pickers write.
 *
 * @param {Object} formula A formula object.
 * @returns {string|null} The id, or null when the formula is empty or more
 *   than a literal.
 */
export function literalFromFormula(formula) {
  if (formula?.mode && formula.mode !== 'simple') {
    return null
  }
  const match = STRING_LITERAL.exec(formula?.formula || '')
  return match ? match[1].replace(/\\(.)/g, '$1') : null
}

/**
 * @param {string} id The picked id.
 * @returns {Object} The formula object of it as a string literal.
 */
export function formulaForLiteral(id) {
  return { formula: id ? toFormulaStringLiteral(id) : '', mode: 'simple' }
}

/**
 * @param {Object} formula A formula object.
 * @returns {boolean} Whether it's empty.
 */
export function isFormulaEmpty(formula) {
  return !formula?.formula?.trim()
}
