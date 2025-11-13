import WorkflowActionService from '@baserow/modules/builder/services/workflowAction'
import PublishedBuilderService from '@baserow/modules/builder/services/publishedBuilder'
import _ from 'lodash'

const updateContext = {
  updateTimeout: null,
  promiseResolve: null,
  lastUpdatedValues: null,
  valuesToUpdate: {},
}

export function populateWorkflowAction(workflowAction) {
  return {
    ...workflowAction,
    _: {
      loading: false,
      dispatching: false,
      dispatchedById: null,
    },
  }
}

const state = {}

const mutations = {
  ADD_ITEM(state, { page, workflowAction }) {
    page.workflowActions.push(populateWorkflowAction(workflowAction))
  },
  SET_ITEMS(state, { page, workflowActions }) {
    page.workflowActions = workflowActions.map((workflowAction) =>
      populateWorkflowAction(workflowAction)
    )
  },
  DELETE_ITEM(state, { page, workflowActionId }) {
    const index = page.workflowActions.findIndex(
      (workflowAction) => workflowAction.id === workflowActionId
    )
    if (index > -1) {
      page.workflowActions.splice(index, 1)
    }
  },
  UPDATE_ITEM(
    state,
    { page, workflowAction: workflowActionToUpdate, values, overwrite = false }
  ) {
    const index = page.workflowActions.findIndex(
      (wa) => wa.id === workflowActionToUpdate.id
    )

    if (index === -1) {
      // The action might have been deleted during the debounced update
      return
    }

    const {
      id,
      page_id: pageId,
      element_id: elementId,
      event,
      order,
    } = page.workflowActions[index]

    if (overwrite) {
      const newValue = populateWorkflowAction({
        id,
        page_id: pageId,
        element_id: elementId,
        event,
        order,
        ...values,
      })
      page.workflowActions.splice(index, 1, newValue)
    } else {
      Object.assign(page.workflowActions[index], values)
    }
  },
  SET_ITEM(state, { page, workflowAction: workflowActionToSet, values }) {
    page.workflowActions = page.workflowActions.map((workflowAction) =>
      workflowAction.id === workflowActionToSet.id
        ? populateWorkflowAction(values)
        : workflowAction
    )
  },
  ORDER_ITEMS(state, { page, order }) {
    page.workflowActions.forEach((workflowAction) => {
      const index = order.findIndex((value) => value === workflowAction.id)
      workflowAction.order = index === -1 ? 0 : index + 1
    })
  },
  SET_LOADING(state, { workflowAction, value }) {
    workflowAction._.loading = value
  },
  SET_DISPATCHING(state, { workflowAction, dispatchedById, isDispatching }) {
    workflowAction._.dispatchedById = dispatchedById
    workflowAction._.dispatching = isDispatching
  },
}

const actions = {
  forceCreate({ commit }, { page, workflowAction }) {
    commit('ADD_ITEM', { page, workflowAction })
  },
  forceDelete({ commit }, { page, workflowActionId }) {
    commit('DELETE_ITEM', { page, workflowActionId })
  },
  forceUpdate({ commit }, { page, workflowAction, values, overwrite }) {
    commit('UPDATE_ITEM', { page, workflowAction, values, overwrite })
  },
  forceSet({ commit }, { page, workflowAction, values }) {
    commit('SET_ITEM', { page, workflowAction, values })
  },
  forceOrder({ commit }, { page, order }) {
    commit('ORDER_ITEMS', { page, order })
  },
  async create(
    { dispatch },
    { page, workflowActionType, eventType, configuration = null }
  ) {
    const { data: workflowAction } = await WorkflowActionService(
      this.$client
    ).create(page.id, workflowActionType, eventType, configuration)

    await dispatch('forceCreate', { page, workflowAction })

    return workflowAction
  },
  async fetch({ commit }, { page }) {
    const { data: workflowActions } = await WorkflowActionService(
      this.$client
    ).fetchAll(page.id)

    commit('SET_ITEMS', { page, workflowActions })
  },
  async fetchPublished({ commit }, { page }) {
    const { data: workflowActions } = await PublishedBuilderService(
      this.$client
    ).fetchWorkflowActions(page.id)

    commit('SET_ITEMS', { page, workflowActions })
  },
  async delete({ dispatch }, { page, workflowAction }) {
    dispatch('forceDelete', { page, workflowActionId: workflowAction.id })

    try {
      await WorkflowActionService(this.$client).delete(workflowAction.id)
    } catch (error) {
      await dispatch('forceCreate', { page, workflowAction })
      throw error
    }
  },
  async updateDebounced(
    { dispatch, commit },
    { page, workflowAction, values }
  ) {
    // These values should not be updated via a regular update request
    const excludeValues = ['order']

    const oldValues = {}
    Object.keys(values).forEach((name) => {
      if (
        Object.prototype.hasOwnProperty.call(workflowAction, name) &&
        !excludeValues.includes(name)
      ) {
        oldValues[name] = workflowAction[name]
        // Accumulate the changed values to send all the ongoing changes with the
        // final request. Ensure that the values are cloned by calling `structuredClone`,
        // as there is a (currently) unexplained issue with an `OpenPage` workflow action
        // `page_parameter` not being cloned properly.
        updateContext.valuesToUpdate[name] = structuredClone(values[name])
      }
    })

    await dispatch('forceUpdate', {
      page,
      workflowAction,
      values: updateContext.valuesToUpdate,
      overwrite: !!updateContext.valuesToUpdate.type,
    })

    return new Promise((resolve, reject) => {
      const fire = async () => {
        commit('SET_LOADING', { workflowAction, value: true })
        const toUpdate = updateContext.valuesToUpdate
        updateContext.valuesToUpdate = {}
        try {
          const { data } = await WorkflowActionService(this.$client).update(
            workflowAction.id,
            toUpdate
          )
          updateContext.lastUpdatedValues = null

          excludeValues.forEach((name) => {
            delete data[name]
          })

          await dispatch('forceUpdate', {
            page,
            workflowAction,
            values: data,
          })
          resolve()
        } catch (error) {
          await dispatch('forceUpdate', {
            page,
            workflowAction,
            values: updateContext.lastUpdatedValues,
          })
          updateContext.lastUpdatedValues = null
          reject(error)
        }
        updateContext.lastUpdatedValues = null
        commit('SET_LOADING', { workflowAction, value: false })
      }

      if (updateContext.promiseResolve) {
        updateContext.promiseResolve()
        updateContext.promiseResolve = null
      }

      clearTimeout(updateContext.updateTimeout)

      if (!updateContext.lastUpdatedValues) {
        updateContext.lastUpdatedValues = oldValues
      }

      updateContext.updateTimeout = setTimeout(fire, 500)
      updateContext.promiseResolve = resolve
    })
  },
  async dispatchAction({ dispatch }, { workflowActionId, data, files }) {
    const { data: result } = await WorkflowActionService(this.$client).dispatch(
      workflowActionId,
      data,
      files
    )
    return result
  },
  async order({ commit, getters }, { page, order, element = null }) {
    const workflowActions =
      element !== null
        ? getters.getElementWorkflowActions(page, element.id)
        : getters.getWorkflowActions(page)

    const oldOrder = workflowActions.map(({ id }) => id)

    commit('ORDER_ITEMS', { page, order })

    try {
      await WorkflowActionService(this.$client).order(
        page.id,
        order,
        element.id
      )
    } catch (error) {
      commit('ORDER_ITEMS', { page, order: oldOrder })
      throw error
    }
  },
  setDispatching(
    { commit },
    { workflowAction, dispatchedById, isDispatching }
  ) {
    commit('SET_DISPATCHING', {
      workflowAction,
      dispatchedById,
      isDispatching,
    })
  },
}

const getters = {
  getWorkflowActions: (state) => (page) => {
    return page.workflowActions.map((w) => w).sort((a, b) => a.order - b.order)
  },
  getWorkflowActionById: (state, getters) => (page, workflowActionId) => {
    return getters
      .getWorkflowActions(page)
      .find((workflowAction) => workflowAction.id === workflowActionId)
  },
  getElementWorkflowActions: (state) => (page, elementId) => {
    return page.workflowActions
      .filter((workflowAction) => workflowAction.element_id === elementId)
      .sort((a, b) => a.order - b.order)
  },
  getElementPreviousWorkflowActions:
    (state, getters) => (page, elementId, workflowAction) => {
      return _.takeWhile(
        getters
          .getElementWorkflowActions(page, elementId)
          .filter(
            (workflowActionToFilter) =>
              workflowActionToFilter.event === workflowAction.event
          ),
        (workflowActionAll) => workflowActionAll.id !== workflowAction.id
      )
    },
  getLoading: (state) => (workflowAction) => {
    return workflowAction._?.loading
  },
  getDispatching: (state) => (workflowAction, dispatchedById) => {
    return (
      workflowAction._.dispatching &&
      workflowAction._.dispatchedById === dispatchedById
    )
  },
}

export default {
  namespaced: true,
  state,
  mutations,
  actions,
  getters,
}
