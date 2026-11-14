import { DataProviderType } from '@baserow/modules/core/dataProviderTypes'

export const TRIGGER_FIRED_AT_PATH = 'fired_at'
export const TRIGGER_ROWS_PATH = 'rows'

/**
 * The payload a trigger service delivers when it fires, offered to the
 * trigger's opening-message formula as `trigger.<property>`. The schema comes
 * from the trigger's service type, so no trigger type is special-cased here. A
 * list payload is offered as `trigger.rows`, next to the values its service
 * type describes the event with, like `trigger.count`. Every trigger also
 * offers `trigger.fired_at`, which the agent computes and which wins over a
 * service property of that name.
 */
export class TriggerDataProviderType extends DataProviderType {
  static getType() {
    return 'trigger'
  }

  get name() {
    return this.app.$i18n.t('agent.triggerData')
  }

  /**
   * @param {object} applicationContext Holds the trigger the message opens.
   * @returns {object|null} The schema of the trigger's data, or null when its
   *   type isn't registered.
   */
  getDataSchema(applicationContext) {
    const service = applicationContext?.trigger?.service
    if (!service?.type || !this.app.$registry.exists('service', service.type)) {
      return null
    }
    const serviceType = this.app.$registry.get('service', service.type)
    const schema = serviceType.getDataSchema(service)
    const properties = serviceType.returnsList(service)
      ? {
          [TRIGGER_ROWS_PATH]: {
            type: 'array',
            items: { type: 'object', properties: {} },
            ...schema,
            title: this.app.$i18n.t('agent.triggerRows'),
          },
          ...serviceType.getEventContextSchema(service),
        }
      : schema?.properties
    return {
      type: 'object',
      title: this.name,
      properties: {
        ...properties,
        [TRIGGER_FIRED_AT_PATH]: {
          type: 'string',
          title: this.app.$i18n.t('agent.triggerFiredAt'),
        },
      },
    }
  }
}

/** Formula paths use stable IDs; titles follow editable input names. */
export class ActionInputDataProviderType extends DataProviderType {
  static getType() {
    return 'tool_input'
  }

  get name() {
    return this.app.$i18n.t('agent.actionInputs')
  }

  getDataSchema(applicationContext) {
    return {
      type: 'object',
      title: this.name,
      properties: Object.fromEntries(
        (applicationContext?.action?.inputs || []).map((input) => [
          input.id,
          {
            type: input.type === 'email' ? 'string' : input.type,
            title: input.name,
            description: input.description,
          },
        ])
      ),
    }
  }
}
