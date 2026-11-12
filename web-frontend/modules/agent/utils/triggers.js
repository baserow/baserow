import { toFormulaStringLiteral } from '@baserow/modules/core/formula'
import { TRIGGER_FIRED_AT_PATH } from '@baserow/modules/agent/dataProviderTypes'

/**
 * The opening message of a new trigger: its name and the time it fired, which
 * suits every trigger type. It is built the way the simple-mode editor emits
 * text followed by a data chip, so it opens as such.
 *
 * @param {Function} t The translate function.
 * @param {object} serviceType The trigger's service type.
 * @returns {object} The message formula object.
 */
export function defaultTriggerMessage(t, serviceType) {
  const firedAt = t('agent.triggerDefaultMessage', {
    trigger: serviceType.name,
  })
  const text = toFormulaStringLiteral(`${firedAt} `)
  return {
    formula: `concat(${text}, get('trigger.${TRIGGER_FIRED_AT_PATH}'))`,
    mode: 'simple',
    version: '0.1',
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
