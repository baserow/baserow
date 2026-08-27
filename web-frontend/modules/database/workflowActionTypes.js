import { WorkflowActionType } from '@baserow/modules/core/workflowActionTypes'
import DatabaseWorkflowActionWithService from '@baserow/modules/database/components/field/DatabaseWorkflowActionWithService'
import OpenUrlWorkflowActionForm from '@baserow/modules/database/components/field/OpenUrlWorkflowActionForm'
import {
  LocalBaserowCreateRowWorkflowServiceType,
  LocalBaserowUpdateRowWorkflowServiceType,
  LocalBaserowDeleteRowWorkflowServiceType,
} from '@baserow/modules/integrations/localBaserow/serviceTypes'
import { resolveFormula } from '@baserow/modules/core/formula'
import RuntimeFormulaContext from '@baserow/modules/core/runtimeFormulaContext'
import {
  encodeUrlWhitespace,
  urlWithAllowedProtocol,
} from '@baserow/modules/database/utils/buttonField'
import { referencedActionIds } from '@baserow/modules/database/utils/workflowActionFormulas'
import {
  workflowActionConfig,
  workflowActionKey,
} from '@baserow/modules/database/utils/workflowActionReconciliation'

// What the backend's own schema calls these, taken from a generated one rather
// than guessed. Only the shapes that change how a node renders are worth
// deriving: an array or an object can have children, everything else is a leaf.
// A number field really is a string, since the API returns it as one.
const JSON_TYPE_BY_FIELD_TYPE = {
  boolean: 'boolean',
  single_select: 'object',
  file: 'array',
  link_row: 'array',
  multiple_select: 'array',
  multiple_collaborators: 'array',
}

/**
 * Whether an action can be read by a later one. A type that returns nothing
 * contributes no node to the data explorer, and the dispatch fails the whole
 * click on a reference to one, so changing an action's type breaks every
 * reference to it just as moving it does.
 */
function producesResult(app, action) {
  if (!action?.type) {
    return false
  }
  return (
    app.$registry.get('databaseWorkflowActionType', action.type)
      .producesResult === true
  )
}

/**
 * Whether an action references one that no longer precedes it or no longer
 * returns anything, which a reorder, a delete or a type change can leave
 * behind. The reference is kept rather than cleared, so putting the other
 * action back makes it valid again.
 */
function staleReferenceError(app, workflowAction, applicationContext) {
  const actions = applicationContext?.workflowActions
  if (!Array.isArray(actions)) {
    return null
  }
  const index = actions.findIndex(
    (action) => workflowActionKey(action) === workflowActionKey(workflowAction)
  )
  if (index === -1) {
    return null
  }
  const before = new Map(
    actions
      .slice(0, index)
      .map((action) => [String(workflowActionKey(action)), action])
  )
  const referenced = referencedActionIds(
    workflowActionConfig(workflowAction)
  ).map(String)

  if (referenced.some((id) => !before.has(id))) {
    return app.$i18n.t('databaseWorkflowActionType.staleReference')
  }
  if (referenced.some((id) => !producesResult(app, before.get(id)))) {
    return app.$i18n.t('databaseWorkflowActionType.unreadableReference')
  }
  return null
}

/**
 * Base for a database workflow action backed by a service. No `execute`: a
 * click dispatches the sequence server side, so nothing runs in the browser.
 */
export class DatabaseWorkflowActionServiceType extends WorkflowActionType {
  get form() {
    return DatabaseWorkflowActionWithService
  }

  get label() {
    return this.serviceType.name
  }

  get icon() {
    return this.serviceType.icon
  }

  get serviceType() {
    throw new Error('Must be set on the type.')
  }

  /**
   * A row action returns the row it wrote, which a later action can read.
   */
  get producesResult() {
    return true
  }

  /**
   * Whether the form offers field mappings, and so needs the target table's
   * fields fetched for it.
   */
  get mapsFields() {
    return false
  }

  getFormProps({ workflowAction, database }) {
    return { workflowAction, database }
  }

  getErrorMessage(workflowAction, applicationContext) {
    const inherited = super.getErrorMessage(workflowAction, applicationContext)
    if (inherited) {
      return inherited
    }
    if (!workflowAction.service?.table_id) {
      return this.app.$i18n.t('databaseWorkflowActionType.noTable')
    }
    return staleReferenceError(this.app, workflowAction, applicationContext)
  }

  getNewActionValues() {
    return { service: {} }
  }

  /**
   * Describes the row this action returns, so a later action can reference it.
   *
   * Derived from the target table's fields, which the action forms report up
   * to the sub-form, and filled out per field from the schema the backend
   * built for a saved action, which knows what a composite field contains.
   */
  getDataSchema(applicationContext, workflowAction) {
    const service = workflowAction.service
    const fields = applicationContext?.tableFields?.[service?.table_id]
    const savedProperties = service?.schema?.properties

    // Which fields exist is the fetched list's to say, since the saved schema
    // describes whichever table the action pointed at when it was last saved
    // and the editor buffers a table change without clearing it. Until that
    // fetch lands the saved schema is all there is.
    if (!fields) {
      const saved = service?.schema
      if (saved?.properties) {
        return {
          ...saved,
          title: this.label,
          properties: this.withoutWriteOnly(saved.properties),
        }
      }
      return null
    }

    return {
      type: 'object',
      title: this.label,
      properties: {
        id: {
          type: 'number',
          // "Id", matching the schema the backend builds, so the node does
          // not rename itself the first time the action is saved.
          title: this.app.$i18n.t('dataProviderTypes.previousActionRowId'),
        },
        ...Object.fromEntries(
          fields
            .filter((field) => !this.isWriteOnly(field))
            .map((field) => {
              const key = `field_${field.id}`
              // Field ids are unique across tables, so a repointed action
              // matches nothing of the table it used to write to.
              return [
                key,
                {
                  type: JSON_TYPE_BY_FIELD_TYPE[field.type] ?? 'string',
                  ...savedProperties?.[key],
                  title: field.name,
                  metadata: field,
                },
              ]
            })
        ),
      },
    }
  }

  isWriteOnly(field) {
    return this.app.$registry.get('field', field.type).isWriteOnlyField(field)
  }

  /**
   * The dispatch refuses to read a write only field, so offering one would
   * only build a formula that fails on click.
   */
  withoutWriteOnly(properties) {
    return Object.fromEntries(
      Object.entries(properties).filter(
        ([, property]) =>
          !property.metadata?.type || !this.isWriteOnly(property.metadata)
      )
    )
  }
}

/**
 * Opens a URL in the browser. No service: the backend hands it back to the
 * client to run, so this extends the core type rather than the one above.
 */
export class OpenUrlWorkflowActionType extends WorkflowActionType {
  static getType() {
    return 'open_url'
  }

  getOrder() {
    return 5
  }

  get form() {
    return OpenUrlWorkflowActionForm
  }

  get label() {
    return this.app.$i18n.t('databaseWorkflowActionType.openUrl')
  }

  get icon() {
    return 'iconoir-link'
  }

  /**
   * The form needs no context beyond the default values it already gets.
   */
  getFormProps() {
    return {}
  }

  /**
   * Opening a URL produces nothing later actions can read, so it contributes
   * no node to the data explorer.
   */
  getDataSchema() {
    return null
  }

  get producesResult() {
    return false
  }

  getErrorMessage(workflowAction, applicationContext) {
    const inherited = super.getErrorMessage(workflowAction, applicationContext)
    if (inherited) {
      return inherited
    }
    if (!workflowAction.url?.formula) {
      return this.app.$i18n.t('databaseWorkflowActionType.noUrl')
    }
    return staleReferenceError(this.app, workflowAction, applicationContext)
  }

  /**
   * Nothing to seed: the form emits its own defaults on mount.
   */
  getNewActionValues() {
    return {}
  }

  /**
   * Resolves the action's URL formula against the clicked row and what the
   * actions before it returned.
   *
   * `fields` stringifies every value, which is what a URL needs; `row` returns
   * raw types and is for action arguments (ADR 006 section 4). A formula that
   * resolves to nothing comes back as an empty string; one that throws is left
   * to `execute`, which reports it.
   */
  resolveUrl(workflowAction, { row, fields, previousActionResults = {} }) {
    const formulaObject = workflowAction.url
    if (!formulaObject?.formula) {
      return ''
    }
    const dataProviders = {
      fields: this.app.$registry.get('databaseDataProvider', 'fields'),
      previous_action: this.app.$registry.get(
        'databaseDataProvider',
        'previous_action'
      ),
    }
    const runtimeFormulaContext = new Proxy(
      new RuntimeFormulaContext(dataProviders, {
        row,
        fields,
        previousActionResults,
      }),
      {
        get(target, prop) {
          return target.get(prop)
        },
      }
    )
    const resolved = resolveFormula(
      formulaObject,
      { get: (name) => this.app.$registry.get('runtimeFormulaFunction', name) },
      runtimeFormulaContext
    )
    if (resolved === null || resolved === undefined) {
      return ''
    }
    return encodeUrlWhitespace(`${resolved}`.trim())
  }

  /**
   * @returns {Promise<Boolean>} Whether the action ran. `false` stops the
   *   client actions after it, which would otherwise navigate away from the
   *   message this one just raised.
   */
  async execute({ workflowAction, applicationContext }) {
    let url
    try {
      url = urlWithAllowedProtocol(
        this.resolveUrl(workflowAction, applicationContext)
      )
    } catch (error) {
      // Nothing here may throw: this runs from a click handler, where a
      // rejection would go unhandled.
      url = ''
    }

    // Empty means the formula did not resolve for this row, or it built a
    // protocol we refuse to open. Say so instead of going nowhere.
    if (!url) {
      await this.app.$store.dispatch('toast/error', {
        title: this.app.$i18n.t('openUrlWorkflowAction.invalidUrlTitle'),
        message: this.app.$i18n.t('openUrlWorkflowAction.invalidUrlMessage'),
      })
      return false
    }

    if (workflowAction.target === 'blank') {
      window.open(url, '_blank', 'noopener,noreferrer')
    } else {
      window.location.href = url
    }
    return true
  }
}

export class LocalBaserowCreateRowWorkflowActionType extends DatabaseWorkflowActionServiceType {
  static getType() {
    return 'local_baserow_create_row'
  }

  getOrder() {
    return 10
  }

  get mapsFields() {
    return true
  }

  get serviceType() {
    return this.app.$registry.get(
      'service',
      LocalBaserowCreateRowWorkflowServiceType.getType()
    )
  }
}

export class LocalBaserowUpdateRowWorkflowActionType extends DatabaseWorkflowActionServiceType {
  static getType() {
    return 'local_baserow_update_row'
  }

  getOrder() {
    return 20
  }

  get mapsFields() {
    return true
  }

  get serviceType() {
    return this.app.$registry.get(
      'service',
      LocalBaserowUpdateRowWorkflowServiceType.getType()
    )
  }
}

export class LocalBaserowDeleteRowWorkflowActionType extends DatabaseWorkflowActionServiceType {
  static getType() {
    return 'local_baserow_delete_row'
  }

  getOrder() {
    return 30
  }

  /**
   * The row is gone, so there is nothing for a later action to read.
   */
  getDataSchema() {
    return null
  }

  get producesResult() {
    return false
  }

  get serviceType() {
    return this.app.$registry.get(
      'service',
      LocalBaserowDeleteRowWorkflowServiceType.getType()
    )
  }
}
