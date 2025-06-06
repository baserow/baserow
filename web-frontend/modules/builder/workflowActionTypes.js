import { WorkflowActionType } from '@baserow/modules/core/workflowActionTypes'
import NotificationWorkflowActionForm from '@baserow/modules/builder/components/workflowAction/NotificationWorkflowActionForm.vue'
import OpenPageWorkflowActionForm from '@baserow/modules/builder/components/workflowAction/OpenPageWorkflowActionForm'
import WorkflowActionWithService from '@baserow/modules/builder/components/workflowAction/WorkflowActionWithService.vue'
import RefreshDataSourceWorkflowActionForm from '@baserow/modules/builder/components/workflowAction/RefreshDataSourceWorkflowActionForm.vue'
import { CoreHTTPRequestServiceType } from '@baserow/modules/integrations/core/serviceTypes'
import {
  LocalBaserowCreateRowWorkflowServiceType,
  LocalBaserowUpdateRowWorkflowServiceType,
  LocalBaserowDeleteRowWorkflowServiceType,
} from '@baserow/modules/integrations/localBaserow/serviceTypes'

import { DataProviderType } from '@baserow/modules/core/dataProviderTypes'
import resolveElementUrl from '@baserow/modules/builder/utils/urlResolution'
import { ensureString } from '@baserow/modules/core/utils/validator'
import { pathParametersInError } from '@baserow/modules/builder/utils/params'

export class NotificationWorkflowActionType extends WorkflowActionType {
  static getType() {
    return 'notification'
  }

  get form() {
    return NotificationWorkflowActionForm
  }

  get label() {
    return this.app.i18n.t('workflowActionTypes.notificationLabel')
  }

  execute({ workflowAction: { title, description }, resolveFormula }) {
    return this.app.store.dispatch('toast/info', {
      title: ensureString(resolveFormula(title)),
      message: ensureString(resolveFormula(description)),
    })
  }

  getDataSchema(applicationContext, workflowAction) {
    return null
  }
}

export class OpenPageWorkflowActionType extends WorkflowActionType {
  static getType() {
    return 'open_page'
  }

  get form() {
    return OpenPageWorkflowActionForm
  }

  get label() {
    return this.app.i18n.t('workflowActionTypes.openPageLabel')
  }

  /**
   * Returns whether the open page configuration is valid or not.
   * @param {object} workflowAction - The workflow action to validate.
   * @param {object} param An object containing application context data.
   * @returns true if the open page action is in error
   */
  isInError(workflowAction, { element, builder }) {
    return pathParametersInError(
      workflowAction,
      this.app.store.getters['page/getVisiblePages'](builder)
    )
  }

  execute({
    workflowAction,
    applicationContext: { builder, mode },
    resolveFormula,
  }) {
    const url = resolveElementUrl(
      workflowAction,
      builder,
      this.app.store.getters['page/getVisiblePages'](builder),
      resolveFormula,
      mode
    )

    if (mode === 'editing' || !url) {
      return
    }

    if (url === this.app.router.history.current?.fullPath) {
      // Return early because the user is already on the page.
      return
    }

    if (workflowAction.target !== 'blank') {
      if (!url.startsWith('/')) {
        window.location.href = url
      } else {
        this.app.router.push(url)
      }
    } else {
      window.open(
        url,
        '_blank',
        !url.startsWith('/') ? 'noopener,noreferrer' : ''
      )
    }
  }

  getDataSchema(applicationContext, workflowAction) {
    return null
  }
}

export class LogoutWorkflowActionType extends WorkflowActionType {
  static getType() {
    return 'logout'
  }

  get form() {
    return null
  }

  get label() {
    return this.app.i18n.t('workflowActionTypes.logoutLabel')
  }

  execute({ applicationContext }) {
    return this.app.store.dispatch('userSourceUser/logoff', {
      application: applicationContext.builder,
    })
  }

  getDataSchema(applicationContext, workflowAction) {
    return null
  }
}

export class RefreshDataSourceWorkflowActionType extends WorkflowActionType {
  static getType() {
    return 'refresh_data_source'
  }

  get form() {
    return RefreshDataSourceWorkflowActionForm
  }

  get label() {
    return this.app.i18n.t('workflowActionTypes.refreshDataSourceLabel')
  }

  async execute({ workflowAction, applicationContext }) {
    const {
      workflowActionContext: { dataSourcePage },
    } = applicationContext
    dataSourcePage.elements
      .filter((element) => {
        return element.data_source_id === workflowAction.data_source_id
      })
      .map(async (element) => {
        await this.app.store.dispatch(
          'elementContent/triggerElementContentReset',
          { element }
        )
      })

    const dispatchContext = DataProviderType.getAllDataSourceDispatchContext(
      this.app.$registry.getAll('builderDataProvider'),
      { ...applicationContext }
    )

    await this.app.store.dispatch(
      'dataSourceContent/fetchPageDataSourceContentById',
      {
        page: dataSourcePage,
        dataSourceId: workflowAction.data_source_id,
        dispatchContext,
        mode: applicationContext.mode,
        replace: true,
      }
    )
  }

  getDataSchema(workflowAction) {
    return null
  }
}

export class WorkflowActionServiceType extends WorkflowActionType {
  get form() {
    return WorkflowActionWithService
  }

  get label() {
    return this.serviceType.name
  }

  execute({ workflowAction: { id }, applicationContext, resolveFormula }) {
    const data = DataProviderType.getAllActionDispatchContext(
      this.app.$registry.getAll('builderDataProvider'),
      applicationContext
    )
    const files = {}
    const result = Object.fromEntries(
      Object.entries(data).map(([key, value]) => {
        if (Array.isArray(value)) {
          Object.assign(files, value[1])
          return [key, value[0]]
        }
        return [key, value]
      })
    )
    return this.app.store.dispatch('builderWorkflowAction/dispatchAction', {
      workflowActionId: id,
      data: result,
      files,
    })
  }

  getDataSchema(workflowAction) {
    if (!workflowAction.service) {
      return null
    }

    const serviceSchema = this.serviceType.getDataSchema(workflowAction.service)

    return {
      title: this.label,
      type: 'object',
      properties: serviceSchema?.properties,
    }
  }

  isInError(workflowAction, { element, builder }) {
    return this.serviceType.isInError({ service: workflowAction.service })
  }

  get serviceType() {
    throw new Error('This method must be implemented')
  }
}

export class CoreHTTPRequestWorkflowActionType extends WorkflowActionServiceType {
  static getType() {
    return 'http_request'
  }

  get serviceType() {
    return this.app.$registry.get(
      'service',
      CoreHTTPRequestServiceType.getType()
    )
  }

  getOrder() {
    return 10
  }
}

export class CreateRowWorkflowActionType extends WorkflowActionServiceType {
  static getType() {
    return 'create_row'
  }

  get serviceType() {
    return this.app.$registry.get(
      'service',
      LocalBaserowCreateRowWorkflowServiceType.getType()
    )
  }
}

export class UpdateRowWorkflowActionType extends WorkflowActionServiceType {
  static getType() {
    return 'update_row'
  }

  get serviceType() {
    return this.app.$registry.get(
      'service',
      LocalBaserowUpdateRowWorkflowServiceType.getType()
    )
  }
}

export class DeleteRowWorkflowActionType extends WorkflowActionServiceType {
  static getType() {
    return 'delete_row'
  }

  get serviceType() {
    return this.app.$registry.get(
      'service',
      LocalBaserowDeleteRowWorkflowServiceType.getType()
    )
  }
}
