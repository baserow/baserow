import { WorkflowActionType } from '@baserow/modules/core/workflowActionTypes'
import NotificationWorkflowActionForm from '@baserow/modules/builder/components/workflowAction/NotificationWorkflowActionForm.vue'
import OpenPageWorkflowActionForm from '@baserow/modules/builder/components/workflowAction/OpenPageWorkflowActionForm'
import CreateRowWorkflowActionForm from '@baserow/modules/builder/components/workflowAction/CreateRowWorkflowAction.vue'
import RefreshDataSourceWorkflowActionForm from '@baserow/modules/builder/components/workflowAction/RefreshDataSourceWorkflowActionForm.vue'
import UpdateRowWorkflowActionForm from '@baserow/modules/builder/components/workflowAction/UpdateRowWorkflowAction.vue'

import { DataProviderType } from '@baserow/modules/core/dataProviderTypes'
import resolveElementUrl from '@baserow/modules/builder/utils/urlResolution'
import { ensureString } from '@baserow/modules/core/utils/validator'
import DeleteRowWorkflowActionForm from '@baserow/modules/builder/components/workflowAction/DeleteRowWorkflowActionForm.vue'

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
    applicationContext.page.elements
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
        page: applicationContext.page,
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
  execute({ workflowAction: { id }, applicationContext, resolveFormula }) {
    return this.app.store.dispatch('workflowAction/dispatchAction', {
      workflowActionId: id,
      data: DataProviderType.getAllActionDispatchContext(
        this.app.$registry.getAll('builderDataProvider'),
        applicationContext
      ),
    })
  }

  getDataSchema(workflowAction) {
    if (!workflowAction?.service?.schema) {
      return null
    }
    return {
      title: this.label,
      type: 'object',
      properties: workflowAction?.service?.schema?.properties,
    }
  }
}

export class CreateRowWorkflowActionType extends WorkflowActionServiceType {
  static getType() {
    return 'create_row'
  }

  get form() {
    return CreateRowWorkflowActionForm
  }

  get label() {
    return this.app.i18n.t('workflowActionTypes.createRowLabel')
  }
}

export class UpdateRowWorkflowActionType extends WorkflowActionServiceType {
  static getType() {
    return 'update_row'
  }

  get form() {
    return UpdateRowWorkflowActionForm
  }

  get label() {
    return this.app.i18n.t('workflowActionTypes.updateRowLabel')
  }
}

export class DeleteRowWorkflowActionType extends WorkflowActionServiceType {
  static getType() {
    return 'delete_row'
  }

  get form() {
    return DeleteRowWorkflowActionForm
  }

  get label() {
    return this.app.i18n.t('workflowActionTypes.deleteRowLabel')
  }
}
