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

/**
 * Base for a database workflow action backed by a service.
 *
 * Unlike the builder's equivalent it has no `execute`: a button click
 * dispatches the whole sequence server side, so nothing runs in the browser.
 * The type only supplies what the editor needs to render the action.
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

  getFormProps({ workflowAction, database }) {
    return { workflowAction, database }
  }

  getNewActionValues() {
    return { service: {} }
  }
}

/**
 * Opens a URL in the browser. Backed by no service: the backend never
 * dispatches it, it just hands the action back to the client to run, so this
 * extends the core type rather than the service based one above.
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
   * The form edits the action's own fields, so it needs no context beyond the
   * default values the list already passes it.
   */
  getFormProps() {
    return {}
  }

  /**
   * Nothing to seed: the form emits its own defaults on mount.
   */
  getNewActionValues() {
    return {}
  }

  /**
   * Resolves the action's URL formula for the clicked row.
   *
   * Only the `fields` data provider is offered: a button URL references
   * `fields.field_<id>` and that provider stringifies every value, which is
   * what a URL needs. The `row` provider returns raw types and exists for
   * action arguments instead (ADR 006 section 4).
   *
   * `resolveFormula` swallows a resolution failure and returns null, so a URL
   * pointing at a trashed field ends up here as an empty string rather than a
   * throw.
   */
  resolveUrl(workflowAction, { row, fields }) {
    const formulaObject = workflowAction.url
    if (!formulaObject?.formula) {
      return ''
    }
    const dataProviders = {
      fields: this.app.$registry.get('databaseDataProvider', 'fields'),
    }
    const runtimeFormulaContext = new Proxy(
      new RuntimeFormulaContext(dataProviders, { row, fields }),
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

    // An empty URL means the formula could not be resolved for this row, or
    // it built a protocol we refuse to navigate to. Say so instead of
    // navigating nowhere.
    if (!url) {
      await this.app.$store.dispatch('toast/error', {
        title: this.app.$i18n.t('openUrlWorkflowAction.invalidUrlTitle'),
        message: this.app.$i18n.t('openUrlWorkflowAction.invalidUrlMessage'),
      })
      return
    }

    if (workflowAction.target === 'blank') {
      window.open(url, '_blank', 'noopener,noreferrer')
    } else {
      window.location.href = url
    }
  }
}

export class CreateRowWorkflowActionType extends DatabaseWorkflowActionServiceType {
  static getType() {
    return 'create_row'
  }

  getOrder() {
    return 10
  }

  get serviceType() {
    return this.app.$registry.get(
      'service',
      LocalBaserowCreateRowWorkflowServiceType.getType()
    )
  }
}

export class UpdateRowWorkflowActionType extends DatabaseWorkflowActionServiceType {
  static getType() {
    return 'update_row'
  }

  getOrder() {
    return 20
  }

  get serviceType() {
    return this.app.$registry.get(
      'service',
      LocalBaserowUpdateRowWorkflowServiceType.getType()
    )
  }
}

export class DeleteRowWorkflowActionType extends DatabaseWorkflowActionServiceType {
  static getType() {
    return 'delete_row'
  }

  getOrder() {
    return 30
  }

  get serviceType() {
    return this.app.$registry.get(
      'service',
      LocalBaserowDeleteRowWorkflowServiceType.getType()
    )
  }
}
