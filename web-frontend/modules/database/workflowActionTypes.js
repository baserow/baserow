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
   * Whether the form offers field mappings, and so needs the target table's
   * fields fetched for it.
   */
  get mapsFields() {
    return false
  }

  getFormProps({ workflowAction, database }) {
    return { workflowAction, database }
  }

  getNewActionValues() {
    return { service: {} }
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
   * Nothing to seed: the form emits its own defaults on mount.
   */
  getNewActionValues() {
    return {}
  }

  /**
   * Resolves the action's URL formula for the clicked row.
   *
   * Only the `fields` provider is offered: it stringifies every value, which
   * is what a URL needs. `row` returns raw types and is for action arguments
   * (ADR 006 section 4). A resolution failure comes back as an empty string.
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

    // Empty means the formula did not resolve for this row, or it built a
    // protocol we refuse to open. Say so instead of going nowhere.
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

  get serviceType() {
    return this.app.$registry.get(
      'service',
      LocalBaserowDeleteRowWorkflowServiceType.getType()
    )
  }
}
