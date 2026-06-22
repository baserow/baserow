import { WorkflowActionType } from '@baserow/modules/core/workflowActionTypes'
import NotificationWorkflowActionForm from '@baserow/modules/builder/components/workflowAction/NotificationWorkflowActionForm.vue'
import OpenPageWorkflowActionForm from '@baserow/modules/builder/components/workflowAction/OpenPageWorkflowActionForm'
import WorkflowActionWithService from '@baserow/modules/builder/components/workflowAction/WorkflowActionWithService.vue'
import RefreshDataSourceWorkflowActionForm from '@baserow/modules/builder/components/workflowAction/RefreshDataSourceWorkflowActionForm.vue'
import {
  CoreCSVFileReaderServiceType,
  CoreHTTPRequestServiceType,
  CoreSMTPEmailServiceType,
} from '@baserow/modules/integrations/core/serviceTypes'
import {
  LocalBaserowCreateRowWorkflowServiceType,
  LocalBaserowCreateRowsWorkflowServiceType,
  LocalBaserowUpdateRowWorkflowServiceType,
  LocalBaserowUpdateRowsWorkflowServiceType,
  LocalBaserowDeleteRowWorkflowServiceType,
} from '@baserow/modules/integrations/localBaserow/serviceTypes'
import { AIAgentServiceType } from '@baserow/modules/integrations/ai/serviceTypes'

import { DataProviderType } from '@baserow/modules/core/dataProviderTypes'
import resolveElementUrl from '@baserow/modules/builder/utils/urlResolution'
import { ensureString } from '@baserow/modules/core/utils/validator'
import { pathParametersInError } from '@baserow/modules/builder/utils/params'
import { handleDispatchError } from '@baserow/modules/builder/utils/error'
import { SlackWriteMessageServiceType } from '@baserow/modules/integrations/slack/serviceTypes'

export class NotificationWorkflowActionType extends WorkflowActionType {
  static getType() {
    return 'notification'
  }

  getOrder() {
    return 10
  }

  get icon() {
    return 'iconoir-chat-bubble-empty'
  }

  get form() {
    return NotificationWorkflowActionForm
  }

  get label() {
    return this.app.$i18n.t('workflowActionTypes.notificationLabel')
  }

  execute({ workflowAction: { title, description }, resolveFormula }) {
    return this.app.$store.dispatch('builderToast/info', {
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

  getOrder() {
    return 15
  }

  get icon() {
    return 'iconoir-open-in-window'
  }

  get form() {
    return OpenPageWorkflowActionForm
  }

  get label() {
    return this.app.$i18n.t('workflowActionTypes.openPageLabel')
  }

  /**
   * Returns whether the open page configuration is valid or not.
   * @param {object} workflowAction - The workflow action to validate.
   * @param {object} param An object containing application context data.
   * @returns true if the open page action is in error
   */
  getErrorMessage(workflowAction, applicationContext) {
    if (workflowAction.navigation_type === 'page') {
      if (!workflowAction.navigate_to_page_id) {
        return this.app.$i18n.t(
          'workflowActionTypes.errorNavigateToPageMissing'
        )
      }
      if (
        pathParametersInError(
          workflowAction,
          this.app.$store.getters['page/getVisiblePages'](
            applicationContext.builder
          )
        )
      ) {
        return this.app.$i18n.t('workflowActionTypes.errorPageParameterInError')
      }
    } else if (
      workflowAction.navigation_type === 'custom' &&
      !workflowAction.navigate_to_url
    ) {
      return this.app.$i18n.t('workflowActionTypes.errorNavigationUrlMissing')
    }

    return super.getErrorMessage(workflowAction, applicationContext)
  }

  execute({
    workflowAction,
    applicationContext: { builder, mode },
    resolveFormula,
  }) {
    const url = resolveElementUrl(
      workflowAction,
      builder,
      this.app.$store.getters['page/getVisiblePages'](builder),
      resolveFormula,
      mode
    )

    if (mode === 'editing' || !url) {
      return
    }

    if (url === this.app.$router.currentRoute.value?.fullPath) {
      // Return early because the user is already on the page.
      return
    }

    if (workflowAction.target !== 'blank') {
      if (!url.startsWith('/')) {
        window.location.href = url
      } else {
        this.app.$router.push(url)
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

  getOrder() {
    return 20
  }

  get icon() {
    return 'iconoir-log-out'
  }

  get form() {
    return null
  }

  get label() {
    return this.app.$i18n.t('workflowActionTypes.logoutLabel')
  }

  execute({ applicationContext }) {
    return this.app.$store.dispatch('userSourceUser/logoff', {
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

  getOrder() {
    return 25
  }

  get icon() {
    return 'iconoir-refresh'
  }

  get form() {
    return RefreshDataSourceWorkflowActionForm
  }

  get label() {
    return this.app.$i18n.t('workflowActionTypes.refreshDataSourceLabel')
  }

  getErrorMessage(workflowAction, applicationContext) {
    if (!workflowAction.data_source_id) {
      return this.app.$i18n.t('workflowActionTypes.errorDataSourceMissing')
    }

    return super.getErrorMessage(workflowAction, applicationContext)
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
        await this.app.$store.dispatch(
          'elementContent/triggerElementContentReset',
          { element }
        )
      })

    const dispatchContext = DataProviderType.getAllDataSourceDispatchContext(
      this.app.$registry.getAll('builderDataProvider'),
      { ...applicationContext }
    )

    try {
      await this.app.$store.dispatch(
        'dataSourceContent/fetchPageDataSourceContentById',
        {
          page: dataSourcePage,
          dataSourceId: workflowAction.data_source_id,
          dispatchContext,
          mode: applicationContext.mode,
          replace: true,
        }
      )
    } catch (error) {
      const dataSource = this.app.$store.getters[
        'dataSource/getPageDataSourceById'
      ](applicationContext.page, workflowAction.data_source_id)
      handleDispatchError(
        error,
        this.app,
        this.app.$i18n.t('builderToast.errorDataSourceDispatch', {
          name: dataSource.name,
        })
      )
    }
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

  get icon() {
    return this.serviceType.icon
  }

  get image() {
    return this.serviceType.image
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
    return this.app.$store.dispatch('builderWorkflowAction/dispatchAction', {
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

    if (serviceSchema) {
      return {
        ...serviceSchema,
        title: this.label,
      }
    }
    return null
  }

  getErrorMessage(workflowAction, applicationContext) {
    const serviceError = this.serviceType.getErrorMessage({
      service: workflowAction.service,
    })

    if (serviceError) {
      return serviceError
    }

    return super.getErrorMessage(workflowAction, applicationContext)
  }

  prepareValuePath(workflowAction, path) {
    return this.serviceType.prepareValuePath(workflowAction.service, path)
  }

  get returnsList() {
    return Boolean(this.serviceType.returnsList)
  }

  get serviceType() {
    throw new Error('This method must be implemented')
  }

  isDeactivatedReason({ workspace }) {
    const serviceReason = this.serviceType.isDeactivatedReason({ workspace })
    if (serviceReason) {
      return serviceReason
    }
    return null
  }

  getDeactivatedClickModal({ workspace }) {
    return this.serviceType.getDeactivatedClickModal({ workspace })
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
    return 60
  }
}

export class CoreSMTPEmailWorkflowActionType extends WorkflowActionServiceType {
  static getType() {
    return 'smtp_email'
  }

  get serviceType() {
    return this.app.$registry.get('service', CoreSMTPEmailServiceType.getType())
  }

  getOrder() {
    return 50
  }
}

export class CoreCSVFileReaderWorkflowActionType extends WorkflowActionServiceType {
  static getType() {
    return 'csv_file_reader'
  }

  get serviceType() {
    return this.app.$registry.get(
      'service',
      CoreCSVFileReaderServiceType.getType()
    )
  }

  getOrder() {
    return 75
  }
}

export class CreateRowWorkflowActionType extends WorkflowActionServiceType {
  static getType() {
    return 'create_row'
  }

  getOrder() {
    return 30
  }

  get serviceType() {
    return this.app.$registry.get(
      'service',
      LocalBaserowCreateRowWorkflowServiceType.getType()
    )
  }
}

export class LocalBaserowCreateRowsWorkflowActionType extends WorkflowActionServiceType {
  static getType() {
    return 'local_baserow_create_rows'
  }

  getOrder() {
    return 35
  }

  get serviceType() {
    return this.app.$registry.get(
      'service',
      LocalBaserowCreateRowsWorkflowServiceType.getType()
    )
  }

  get returnsList() {
    return true
  }
}

export class UpdateRowWorkflowActionType extends WorkflowActionServiceType {
  static getType() {
    return 'update_row'
  }

  getOrder() {
    return 40
  }

  get serviceType() {
    return this.app.$registry.get(
      'service',
      LocalBaserowUpdateRowWorkflowServiceType.getType()
    )
  }
}

export class LocalBaserowUpdateRowsWorkflowActionType extends WorkflowActionServiceType {
  static getType() {
    return 'local_baserow_update_rows'
  }

  getOrder() {
    return 42
  }

  get serviceType() {
    return this.app.$registry.get(
      'service',
      LocalBaserowUpdateRowsWorkflowServiceType.getType()
    )
  }

  get returnsList() {
    return true
  }
}

export class DeleteRowWorkflowActionType extends WorkflowActionServiceType {
  static getType() {
    return 'delete_row'
  }

  getOrder() {
    return 45
  }

  get serviceType() {
    return this.app.$registry.get(
      'service',
      LocalBaserowDeleteRowWorkflowServiceType.getType()
    )
  }
}

export class AIAgentWorkflowActionType extends WorkflowActionServiceType {
  static getType() {
    return 'ai_agent'
  }

  getOrder() {
    return 70
  }

  get serviceType() {
    return this.app.$registry.get('service', AIAgentServiceType.getType())
  }
}

export class SlackWriteMessageWorkflowActionType extends WorkflowActionServiceType {
  static getType() {
    return 'slack_write_message'
  }

  getOrder() {
    return 55
  }

  get serviceType() {
    return this.app.$registry.get(
      'service',
      SlackWriteMessageServiceType.getType()
    )
  }
}
