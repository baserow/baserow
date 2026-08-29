import { DataProviderType } from '@baserow/modules/core/dataProviderTypes'

const INPUT_TYPE_TO_SCHEMA_TYPE = {
  string: 'string',
  number: 'number',
  boolean: 'boolean',
}

/**
 * Exposes the runtime inputs the user declared on an agent action tool in the
 * data explorer, so service formulas can reference the values the model
 * provides when calling the tool via `get('tool_input.<name>')`.
 */
export class ToolInputDataProviderType extends DataProviderType {
  static getType() {
    return 'tool_input'
  }

  get name() {
    return this.app.$i18n.t('agentDataProviderType.toolInput')
  }

  getDataSchema(applicationContext) {
    const inputs = applicationContext?.tool?.config?.inputs || []
    const properties = {}
    for (const input of inputs) {
      if (!input.name) {
        continue
      }
      properties[input.name] = {
        type: INPUT_TYPE_TO_SCHEMA_TYPE[input.type] || 'string',
        title: input.name,
      }
    }
    return { type: 'object', properties }
  }
}
