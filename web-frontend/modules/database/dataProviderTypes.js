import { DataProviderType } from '@baserow/modules/core/dataProviderTypes'
import { getValueAtPath } from '@baserow/modules/core/utils/object'
import { workflowActionKey } from '@baserow/modules/database/utils/workflowActionReconciliation'

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

/**
 * Exposes what the earlier actions of a click returned, so a later action can
 * use them. An action is offered only the actions before it in the list, which
 * is what keeps a reference pointing backwards.
 */
export class PreviousActionDataProviderType extends DataProviderType {
  static getType() {
    return 'previous_action'
  }

  get name() {
    return this.app.$i18n.t('dataProviderTypes.previousActionName')
  }

  getDataContent(applicationContext) {
    return applicationContext.previousActionResults || {}
  }

  /**
   * The actions before the one whose formula is being edited.
   */
  previousActions(applicationContext) {
    const actions = applicationContext.workflowActions || []
    const current = applicationContext.workflowAction
    if (!current) {
      return []
    }
    const index = actions.findIndex(
      (action) => workflowActionKey(action) === workflowActionKey(current)
    )
    return index === -1 ? [] : actions.slice(0, index)
  }

  getDataSchema(applicationContext) {
    const schemas = this.previousActions(applicationContext)
      .map((action) => [
        action,
        action.type
          ? this.app.$registry
              .get('databaseWorkflowActionType', action.type)
              .getDataSchema(action, applicationContext)
          : null,
      ])
      .filter(([, schema]) => schema)

    // Two actions of the same type would otherwise be indistinguishable.
    const seen = {}
    const properties = Object.fromEntries(
      schemas.map(([action, schema]) => {
        seen[action.type] = (seen[action.type] || 0) + 1
        const suffix = seen[action.type] > 1 ? ` ${seen[action.type]}` : ''
        return [
          workflowActionKey(action),
          { ...schema, title: `${schema.title}${suffix}` },
        ]
      })
    )

    return { type: 'object', properties }
  }

  /**
   * Mirrors the backend provider, which raises rather than resolving a broken
   * reference to nothing. Resolving to nothing here would leave a hole in a URL
   * and open it anyway, which is the whole failure this phase avoids.
   */
  getDataChunk(applicationContext, path) {
    const [actionId, ...rest] = path
    const results = applicationContext.previousActionResults
    if (results === undefined) {
      // The editor resolves formulas for its own preview long before anything
      // has run, so there is nothing to read yet and nothing wrong with that.
      // Only a real click carries results, and only there is a broken
      // reference a failure.
      return null
    }
    const entry = results[actionId]
    if (entry === undefined) {
      throw new Error(`Action ${actionId} did not run in this click.`)
    }
    if (rest.length === 0) {
      return entry.data
    }
    if (entry.data === null || typeof entry.data !== 'object') {
      throw new Error('The previous action returned nothing to read.')
    }
    const [fieldRef, ...tail] = rest
    // The result is keyed by field name, the path by `field_<id>`. A field the
    // result did not carry was deleted after the reference was written.
    const key = entry.fieldNames?.[fieldRef]
    if (key === undefined && fieldRef.startsWith('field_')) {
      throw new Error(`${fieldRef} is not in the previous action's result.`)
    }
    return getValueAtPath(entry.data, [key ?? fieldRef, ...tail])
  }
}
