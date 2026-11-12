import { DataProviderType } from '@baserow/modules/core/dataProviderTypes'

export const TRIGGER_FIRED_AT_PATH = 'fired_at'

/**
 * The payload a trigger service delivers when it fires, offered to the
 * trigger's opening-message formula as `trigger.<property>`. The schema comes
 * from the trigger's service type, so no trigger type is special-cased here.
 * Every trigger also offers `trigger.fired_at`, which the agent computes and
 * which wins over a service property of that name.
 */
export class TriggerDataProviderType extends DataProviderType {
  static getType() {
    return 'trigger'
  }

  get name() {
    return this.app.$i18n.t('agent.triggerData')
  }

  getDataSchema(applicationContext) {
    const service = applicationContext?.trigger?.service
    if (!service?.type || !this.app.$registry.exists('service', service.type)) {
      return null
    }
    const schema = this.app.$registry
      .get('service', service.type)
      .getDataSchema(service) || { type: 'object', properties: {} }
    // A list payload is addressed by row index, so it has no place for a sibling.
    if (schema.type !== 'object') return { ...schema, title: this.name }
    return {
      ...schema,
      title: this.name,
      properties: {
        ...schema.properties,
        [TRIGGER_FIRED_AT_PATH]: {
          type: 'string',
          title: this.app.$i18n.t('agent.triggerFiredAt'),
        },
      },
    }
  }
}
