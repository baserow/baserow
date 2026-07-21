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

  /**
   * Resolves get('fields.field_<id>') against the row in the application
   * context, mirroring the backend HumanReadableFieldsDataProviderType.
   */
  getDataChunk(applicationContext, path) {
    const [fieldRef] = path
    const { row, fields } = applicationContext
    if (!row || !fields) {
      return ''
    }
    const field = fields.find((f) => `field_${f.id}` === fieldRef)
    if (!field) {
      return ''
    }
    const value = row[fieldRef]
    if (value === null || value === undefined) {
      return ''
    }
    return this.app.$registry
      .get('field', field.type)
      .toHumanReadableString(field, value)
  }
}
