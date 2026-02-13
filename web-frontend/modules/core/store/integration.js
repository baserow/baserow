import IntegrationService from '@baserow/modules/core/services/integration'

const state = {}

const updateContext = {
  updateTimeout: null,
  promiseResolve: null,
  lastUpdatedValues: null,
}

const mutations = {
  ADD_ITEM(state, { application, integration, beforeId = null }) {
    if (beforeId === null) {
      application.integrations.push(integration)
    } else {
      const insertionIndex = application.integrations.findIndex(
        (e) => e.id === beforeId
      )
      application.integrations.splice(insertionIndex, 0, integration)
    }
  },
  UPDATE_ITEM(
    state,
    { application, integration: integrationToUpdate, values }
  ) {
    application.integrations.forEach((integration) => {
      if (integration.id === integrationToUpdate.id) {
        Object.assign(integration, values)
      }
    })
  },
  DELETE_ITEM(state, { application, integrationId }) {
    const index = application.integrations.findIndex(
      (integration) => integration.id === integrationId
    )
    if (index > -1) {
      application.integrations.splice(index, 1)
    }
  },
  MOVE_ITEM(state, { application, index, oldIndex }) {
    application.integrations.splice(
      index,
      0,
      application.integrations.splice(oldIndex, 1)[0]
    )
  },
  CLEAR_ITEMS(state, { application }) {
    application.integrations = []
  },
}

const actions = {
  forceCreate({ commit }, { application, integration, beforeId = null }) {
    commit('ADD_ITEM', { application, integration, beforeId })
  },
  forceUpdate({ commit }, { application, integration, values }) {
    commit('UPDATE_ITEM', { application, integration, values })
  },
  forceDelete({ commit, getters }, { application, integrationId }) {
    commit('DELETE_ITEM', { application, integrationId })
  },
  forceMove(
    { commit, getters },
    { application, integrationId, beforeIntegrationId }
  ) {
    const currentOrder = getters
      .getIntegrations(application)
      .map((integration) => integration.id)
    const oldIndex = currentOrder.findIndex((id) => id === integrationId)
    const index = beforeIntegrationId
      ? currentOrder.findIndex((id) => id === beforeIntegrationId)
      : getters.getIntegrations.length

    // If the integration is before the beforeIntegration we must decrease the target index by
    // one to compensate the removed integration.
    if (oldIndex < index) {
      commit('MOVE_ITEM', { application, index: index - 1, oldIndex })
    } else {
      commit('MOVE_ITEM', { application, index, oldIndex })
    }
  },
  async create(
    { dispatch },
    { application, integrationType, values, beforeId = null }
  ) {
    const { $registry, $i18n, $client, $config } = this
    const { data: integration } = await IntegrationService($client).create(
      application.id,
      integrationType,
      values,
      beforeId
    )

    await dispatch('forceCreate', { application, integration, beforeId })

    return integration
  },
  async update({ dispatch, getters }, { application, integrationId, values }) {
    const { $registry, $i18n, $client, $config } = this
    const integrationsOfApplication = getters.getIntegrations(application)
    const integration = integrationsOfApplication.find(
      ({ id }) => id === integrationId
    )
    const oldValues = {}
    const newValues = {}
    Object.keys(values).forEach((name) => {
      if (Object.prototype.hasOwnProperty.call(integration, name)) {
        oldValues[name] = integration[name]
        newValues[name] = values[name]
      }
    })

    await dispatch('forceUpdate', {
      application,
      integration,
      values: newValues,
    })

    try {
      await IntegrationService($client).update(integration.id, values)
    } catch (error) {
      await dispatch('forceUpdate', {
        application,
        integration,
        values: oldValues,
      })
      throw error
    }
  },

  async debouncedUpdate(
    { dispatch, getters },
    { application, integrationId, values }
  ) {
    const { $registry, $i18n, $client, $config } = this
    const integration = getters
      .getIntegrations(application)
      .find(({ id }) => id === integrationId)
    const oldValues = {}
    const newValues = {}
    Object.keys(values).forEach((name) => {
      if (Object.prototype.hasOwnProperty.call(integration, name)) {
        oldValues[name] = integration[name]
        newValues[name] = values[name]
      }
    })

    await dispatch('forceUpdate', {
      application,
      integration,
      values: newValues,
    })

    return new Promise((resolve, reject) => {
      const fire = async () => {
        try {
          await IntegrationService($client).update(integration.id, values)
          updateContext.lastUpdatedValues = values
          resolve()
        } catch (error) {
          // Revert to old values on error
          await dispatch('forceUpdate', {
            application,
            integration,
            values: updateContext.lastUpdatedValues,
          })
          reject(error)
        }
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
  async delete({ dispatch, getters }, { application, integrationId }) {
    const { $registry, $i18n, $client, $config } = this
    const integrationsOfApplication = getters.getIntegrations(application)
    const integrationIndex = integrationsOfApplication.findIndex(
      (integration) => integration.id === integrationId
    )
    const integrationToDelete = integrationsOfApplication[integrationIndex]
    const beforeId =
      integrationIndex !== integrationsOfApplication.length - 1
        ? integrationsOfApplication[integrationIndex + 1].id
        : null

    await dispatch('forceDelete', { application, integrationId })

    try {
      await IntegrationService($client).delete(integrationId)
    } catch (error) {
      await dispatch('forceCreate', {
        application,
        integration: integrationToDelete,
        beforeId,
      })
      throw error
    }
  },
  async move(
    { dispatch },
    { application, integrationId, beforeIntegrationId }
  ) {
    const { $registry, $i18n, $client, $config } = this
    await dispatch('forceMove', {
      application,
      integrationId,
      beforeIntegrationId,
    })

    try {
      await IntegrationService($client).move(integrationId, beforeIntegrationId)
    } catch (error) {
      await dispatch('forceMove', {
        application,
        integrationId: beforeIntegrationId,
        beforeIntegrationId: integrationId,
      })
      throw error
    }
  },
  async fetch({ dispatch, commit }, { application }) {
    const { $registry, $i18n, $client, $config } = this
    const { data: integrations } = await IntegrationService($client).fetchAll(
      application.id
    )

    commit('CLEAR_ITEMS', { application })
    await Promise.all(
      integrations.map((integration) =>
        dispatch('forceCreate', { application, integration })
      )
    )

    return integrations
  },
  async duplicate({ getters, dispatch }, { application, integrationId }) {
    const integration = getters.getIntegrations.find(
      (e) => e.id === integrationId
    )
    await dispatch('create', {
      application,
      integrationType: integration.type,
      beforeId: integration.id,
    })
  },
}

const getters = {
  getIntegrations: (state) => (application) => {
    return application?.integrations || []
  },
  getIntegrationById: (state) => (application, id) => {
    return application?.integrations?.find(
      (integration) => integration.id === id
    )
  },
}

export default {
  namespaced: true,
  state,
  getters,
  actions,
  mutations,
}
