import { toFormulaStringLiteral } from '@baserow/modules/core/formula'
import {
  TRIGGER_FIRED_AT_PATH,
  TRIGGER_ROWS_PATH,
} from '@baserow/modules/agent/dataProviderTypes'

/**
 * @param {string} path A path of the trigger's data.
 * @returns {string} The formula reading it, shown as a chip in simple mode.
 */
const triggerData = (path) => `get('trigger.${path}')`

/**
 * @param {object} serviceType The trigger's service type.
 * @param {object} service The trigger's service values.
 * @param {string} template Its event sentence, with `{name}` placeholders.
 * @returns {string[]} The sentence as text literals and data chips, then the
 *   rows of a list payload.
 */
function eventDescriptionArgs(serviceType, service, template) {
  const args = template
    .split(/\{(\w+)\}/)
    .map((part, index) =>
      index % 2 ? triggerData(part) : part && toFormulaStringLiteral(part)
    )
    .filter(Boolean)
  if (serviceType.returnsList(service)) {
    args.push(toFormulaStringLiteral(': '), triggerData(TRIGGER_ROWS_PATH))
  }
  return args
}

/**
 * The opening message of a new trigger, built the way the simple-mode editor
 * emits text and data chips, so it opens as such. A type that describes its
 * event gets that sentence with its values as chips, like "{count} rows were
 * created in {table}: {rows}"; any other gets its name and the time it fired.
 *
 * @param {Function} t The translate function.
 * @param {object} serviceType The trigger's service type.
 * @param {object} service The trigger's service values.
 * @returns {object} The message formula object.
 */
export function defaultTriggerMessage(t, serviceType, service) {
  const template = serviceType.getEventDescriptionTemplate()
  const args = template
    ? eventDescriptionArgs(serviceType, service, template)
    : [
        toFormulaStringLiteral(
          `${t('agent.triggerDefaultMessage', { trigger: serviceType.name })} `
        ),
        triggerData(TRIGGER_FIRED_AT_PATH),
      ]
  return {
    formula: `concat(${args.join(', ')})`,
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
