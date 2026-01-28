import { DataProviderType } from '@baserow/modules/core/dataProviderTypes'

export class FieldsDataProviderType extends DataProviderType {
  static getType() {
    return 'fields'
  }

  get name() {
    return this.app.$i18n.t('dataProviderTypes.fieldsName')
  }

  getDataContent(applicationContext) {
    return ''
  }

  getDataSchema(applicationContext) {
    return {
      type: 'object',
      properties: Object.fromEntries(
        (applicationContext.fields || []).map((field) => [
          `field_${field.id}`,
          {
            title: field.name,
            type: 'string',
          },
        ])
      ),
    }
  }
}
