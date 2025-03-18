import RuntimeFormulaContext from '@baserow/modules/core/runtimeFormulaContext'
import { resolveFormula } from '@baserow/modules/core/formula'
import { uuid } from '@baserow/modules/core/utils/string'

/**
 * This might look like something that belongs in a registry, but it does not.
 *
 * There is no point in making these accessible to plugin writers so there is no
 * registry required.
 */
export class Event {
  constructor({
    i18n,
    store,
    $registry,
    name,
    label,
    applicationContextAdditions = {},
  }) {
    this.i18n = i18n
    this.store = store
    this.$registry = $registry
    this.name = name
    this.label = label
    this.applicationContextAdditions = applicationContextAdditions
  }

  async fire({ workflowActions, applicationContext }) {
    const additionalContext = {}
    const { element, recordIndexPath, builder, page } = applicationContext
    const pages = [page, this.store.getters['page/getSharedPage'](builder)]
    const elementType = this.$registry.get('element', element.type)
    const dispatchedById = elementType.uniqueElementId(element, recordIndexPath)

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
      const workflowActionType = this.$registry.get(
        'workflowAction',
        workflowAction.type
      )

      // If the workflow action refreshes a data source.
      if (workflowAction.data_source_id) {
        // Stash away in the workflow action's context dataSource and
        // the page the dataSource belongs to. It's possible that the page
        // is not `applicationContext.page` - the dataSource could be shared.
        workflowActionContext.dataSource = this.store.getters[
          'dataSource/getPagesDataSourceById'
        ](pages, parseInt(workflowAction.data_source_id))
        workflowActionContext.dataSourcePage = pages.find(
          (page) => page.id === workflowActionContext.dataSource.page_id
        )
      }

      const localResolveFormula = (formula) => {
        const formulaFunctions = {
          get: (name) => {
            return this.$registry.get('runtimeFormulaFunction', name)
          },
        }
        const runtimeFormulaContext = new Proxy(
          new RuntimeFormulaContext(
            this.$registry.getAll('builderDataProvider'),
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

      this.store.dispatch('workflowAction/setDispatching', {
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
      } finally {
        this.store.dispatch('workflowAction/setDispatching', {
          workflowAction,
          dispatchedById: null,
          isDispatching: false,
        })
      }
    }
  }
}

export class ClickEvent extends Event {
  constructor({ namePrefix, labelSuffix, ...rest }) {
    super({
      ...rest,
      name: namePrefix ? `${namePrefix}_click` : 'click',
      label: labelSuffix
        ? `${rest.i18n.t('eventTypes.clickLabel')} ${labelSuffix}`
        : rest.i18n.t('eventTypes.clickLabel'),
    })
  }
}

export class SubmitEvent extends Event {
  constructor(args) {
    super({
      name: 'submit',
      label: args.i18n.t('eventTypes.submitLabel'),
      ...args,
    })
  }
}

export class AfterLoginEvent extends Event {
  constructor(args) {
    super({
      name: 'after_login',
      label: args.i18n.t('eventTypes.afterLoginLabel'),
      ...args,
    })
  }
}
