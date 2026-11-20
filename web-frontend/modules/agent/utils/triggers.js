import { toFormulaStringLiteral } from '@baserow/modules/core/formula'
import { TRIGGER_FIRED_AT_PATH } from '@baserow/modules/agent/dataProviderTypes'

/**
 * A message of text followed by a value of the trigger's data, built the way
 * the simple-mode editor emits text followed by a data chip, so it opens as such.
 *
 * @param {string} text The text before the chip.
 * @param {string} path The path of the value in the trigger's data.
 * @returns {object} The message formula object.
 */
export function textThenTriggerData(text, path) {
  const literal = toFormulaStringLiteral(`${text} `)
  return {
    formula: `concat(${literal}, get('trigger.${path}'))`,
    mode: 'simple',
    version: '0.1',
  }
}

/**
 * A message worded as a sentence whose `{name}` placeholders are values of the
 * trigger's data, built like `textThenTriggerData`, so it opens as text and
 * data chips.
 *
 * @param {string} sentence The sentence, like "{count} rows in {table}".
 * @returns {object} The message formula object.
 */
export function sentenceWithTriggerData(sentence) {
  const args = sentence
    .split(/\{(\w+)\}/)
    .map((part, index) =>
      index % 2
        ? `get('trigger.${part}')`
        : part && toFormulaStringLiteral(part)
    )
    .filter(Boolean)
  return {
    formula: `concat(${args.join(', ')})`,
    mode: 'simple',
    version: '0.1',
  }
}

/**
 * The opening message of a new trigger whose type words none of its own: its
 * name and the time it fired, which suits every trigger type.
 *
 * @param {Function} t The translate function.
 * @param {object} serviceType The trigger's service type.
 * @returns {object} The message formula object.
 */
export function defaultTriggerMessage(t, serviceType) {
  return textThenTriggerData(
    t('agent.triggerDefaultMessage', { trigger: serviceType.name }),
    TRIGGER_FIRED_AT_PATH
  )
}

/**
 * @param {object} registry The app registry.
 * @param {string|null} type The service type of a trigger.
 * @returns {object|null} What an Agent changes about the type, or null when it
 *   hosts the type as it is.
 */
export function agentTriggerTypeOf(registry, type) {
  return type && registry.exists('agentTriggerType', type)
    ? registry.get('agentTriggerType', type)
    : null
}

/**
 * @param {object} registry The app registry.
 * @param {Function} t The translate function.
 * @param {object} serviceType A trigger's service type.
 * @returns {object} The opening message of a new trigger of that type: the one
 *   an Agent words for it, else its name and the time it fired.
 */
export function newTriggerMessage(registry, t, serviceType) {
  return (
    agentTriggerTypeOf(registry, serviceType.type)?.getDefaultMessage() ??
    defaultTriggerMessage(t, serviceType)
  )
}

/**
 * @param {object} registry The app registry.
 * @param {Function} t The translate function.
 * @param {string} type The service type of the trigger.
 * @returns {object} What a new trigger of that type is created with: the type's
 *   default service values and its opening message.
 */
export function newTriggerValues(registry, t, type) {
  const serviceType = registry.get('service', type)
  return {
    type,
    message: newTriggerMessage(registry, t, serviceType),
    service: serviceType.getDefaultValues(null, {}),
  }
}

/**
 * A removed plugin's trigger type is unknown here, and `Registry.get` would throw.
 *
 * @param {object} registry The app registry.
 * @param {string|null} type The service type of a trigger.
 * @returns {object|null} The service type, or null when it isn't registered.
 */
export function serviceTypeOf(registry, type) {
  return type && registry.exists('service', type)
    ? registry.get('service', type)
    : null
}
