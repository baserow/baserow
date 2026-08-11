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
      properties: {
        // Not a field, but a URL commonly needs the clicked row's id.
        id: {
          title: this.app.$i18n.t('dataProviderTypes.rowId'),
          type: 'number',
        },
        ...Object.fromEntries(
          (applicationContext.fields || []).map((field) => [
            `field_${field.id}`,
            {
              title: field.name,
              type: 'string',
            },
          ])
        ),
      },
    }
  }

  /**
   * Resolves get('fields.field_<id>') against the row in the application
   * context, mirroring the backend HumanReadableFieldsDataProviderType.
   */
  getDataChunk(applicationContext, path) {
    const [fieldRef] = path
    const { row, fields } = applicationContext
    // A field this context cannot provide, a hidden one for instance, must
    // fail the resolution rather than silently build a wrong URL.
    if (!row || !fields) {
      throw new Error(`No row context to resolve ${fieldRef}.`)
    }
    if (fieldRef === 'id') {
      return row.id
    }
    const field = fields.find((f) => `field_${f.id}` === fieldRef)
    if (!field) {
      throw new Error(`Field ${fieldRef} can't be resolved in this context.`)
    }
    // An empty cell is legitimately an empty string in the URL.
    const value = row[fieldRef]
    if (value === null || value === undefined) {
      return ''
    }
    return this.app.$registry
      .get('field', field.type)
      .toHumanReadableString(field, value)
  }
}

/**
 * Mirrors the backend `RowDataProviderType`: the clicked row's values with
 * their real types. Separate from `FieldsDataProviderType`, which stringifies
 * everything, right for a URL and wrong for writing (ADR 006 section 4).
 */
export class RowDataProviderType extends DataProviderType {
  static getType() {
    return 'row'
  }

  get name() {
    return this.app.$i18n.t('dataProviderTypes.rowName')
  }

  getDataContent(applicationContext) {
    return ''
  }

  getDataSchema(applicationContext) {
    const { fields = [] } = applicationContext
    return {
      type: 'object',
      properties: {
        // So an update or delete action can target the clicked row.
        id: {
          title: this.app.$i18n.t('dataProviderTypes.rowId'),
          type: 'number',
        },
        ...Object.fromEntries(
          fields.map((field) => [
            `field_${field.id}`,
            {
              title: field.name,
              type: 'string',
            },
          ])
        ),
      },
    }
  }

  /**
   * Resolves get('row.<name>') against the row in the application context.
   * Unlike the human readable provider the value is returned untouched.
   */
  getDataChunk(applicationContext, path) {
    const [name] = path
    const { row } = applicationContext
    if (!row) {
      throw new Error(`No row context to resolve ${name}.`)
    }
    return row[name] ?? null
  }
}
