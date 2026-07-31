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
    // A missing field must fail the resolution so the button renders
    // disabled, instead of silently building a wrong URL. This happens in
    // contexts that can't provide the field, like the link-row picker or a
    // public view where the referenced field is hidden.
    if (!row || !fields) {
      throw new Error(`No row context to resolve ${fieldRef}.`)
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
 * Mirrors the backend `RowDataProviderType`: exposes the clicked row's values
 * with their real types, for a button field's workflow action arguments.
 *
 * Deliberately separate from `FieldsDataProviderType`, which stringifies every
 * value. That is right for a prompt or a URL and wrong for writing a number,
 * date or link into a row (ADR 006 section 4).
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
        // The row's own id, so an update or delete action can target the row
        // that was clicked.
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
