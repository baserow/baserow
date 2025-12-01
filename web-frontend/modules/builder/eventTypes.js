import RuntimeFormulaContext from '@baserow/modules/core/runtimeFormulaContext'
import { resolveFormula } from '@baserow/modules/core/formula'
import { uuid } from '@baserow/modules/core/utils/string'
import { handleDispatchError } from '@baserow/modules/builder/utils/error'

/**
 * This might look like something that belongs in a registry, but it does not.
 *
 * There is no point in making these accessible to plugin writers so there is no
 * registry required.
 */
export class Event {
  constructor({ app, name, label, applicationContextAdditions = {} }) {
    this.app = app
    this.name = name
    this.label = label
    this.applicationContextAdditions = applicationContextAdditions
  }

  async fire({ workflowActions, applicationContext }) {
    const additionalContext = {}
    const { element, builder, page } = applicationContext
    const pages = [page, this.app.store.getters['page/getSharedPage'](builder)]
    const elementType = this.app.$registry.get('element', element.type)
    const dispatchedById = elementType.uniqueElementId({
      element,
      applicationContext,
    })

    /**
     * The currentDispatchId is used to keep track of chained Workflow Actions.
     *
     * When an event (e.g. Button click) triggers multiple Workflow Actions,
     * the backend needs to keep track of them within the context of the event.
     * The backend temporarily saves the intermediate results where appropriate
     * in order to improve security, e.g. when upserting data derived from a
     * Previous Action data provider.
     */
    const currentDispatchId = uuid()

    for (let i = 0; i < workflowActions.length; i += 1) {
      const workflowActionContext = {}
      const workflowAction = workflowActions[i]
      const workflowActionType = this.app.$registry.get(
        'workflowAction',
        workflowAction.type
      )

      // If the workflow action refreshes a data source.
      if (workflowAction.data_source_id) {
        // Stash away in the workflow action's context dataSource and
        // the page the dataSource belongs to. It's possible that the page
        // is not `applicationContext.page` - the dataSource could be shared.
        workflowActionContext.dataSource = this.app.store.getters[
          'dataSource/getPagesDataSourceById'
        ](pages, parseInt(workflowAction.data_source_id))
        workflowActionContext.dataSourcePage = pages.find(
          (page) => page.id === workflowActionContext.dataSource.page_id
        )
      }

      const localResolveFormula = (formula) => {
        const formulaFunctions = {
          get: (name) => {
            return this.app.$registry.get('runtimeFormulaFunction', name)
          },
        }
        const runtimeFormulaContext = new Proxy(
          new RuntimeFormulaContext(
            this.app.$registry.getAll('builderDataProvider'),
            {
              ...applicationContext,
              ...this.applicationContextAdditions,
              previousActionResults: additionalContext,
            }
          ),
          {
            get(target, prop) {
              return target.get(prop)
            },
          }
        )
        try {
          return resolveFormula(
            formula,
            formulaFunctions,
            runtimeFormulaContext
          )
        } catch {
          return ''
        }
      }

      this.app.store.dispatch('builderWorkflowAction/setDispatching', {
        workflowAction,
        dispatchedById,
        isDispatching: true,
      })
      try {
        additionalContext[workflowAction.id] = await workflowActionType.execute(
          {
            workflowAction,
            additionalContext,
            applicationContext: {
              ...applicationContext,
              workflowActionContext,
              previousActionResults: additionalContext,
              currentDispatchId,
            },
            resolveFormula: localResolveFormula,
          }
        )
      } catch (e) {
        handleDispatchError(
          e,
          this.app,
          this.app.i18n.t('builderToast.errorWorkflowActionDispatch', {
            name: workflowActionType.label,
          })
        )
      } finally {
        this.app.store.dispatch('builderWorkflowAction/setDispatching', {
          workflowAction,
          dispatchedById: null,
          isDispatching: false,
        })
      }
    }
  }
}

export class ClickEvent extends Event {
  constructor({ namePrefix, labelSuffix, app, applicationContextAdditions }) {
    super({
      app,
      applicationContextAdditions,
      name: namePrefix ? `${namePrefix}_click` : 'click',
      label: labelSuffix
        ? `${app.i18n.t('eventTypes.clickLabel')} ${labelSuffix}`
        : app.i18n.t('eventTypes.clickLabel'),
    })
  }
}

export class SubmitEvent extends Event {
  constructor(args) {
    super({
      name: 'submit',
      label: args.app.i18n.t('eventTypes.submitLabel'),
      ...args,
    })
  }
}

export class AfterLoginEvent extends Event {
  constructor(args) {
    super({
      name: 'after_login',
      label: args.app.i18n.t('eventTypes.afterLoginLabel'),
      ...args,
    })
  }
}
