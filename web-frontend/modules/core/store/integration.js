import IntegrationService from '@baserow/modules/core/services/integration'

// How many times a fetch asks again when the list changed while it was open.
// Bounded: a list changing this often is not settling, and the caller is told
// nothing was loaded rather than made to wait.
const FETCH_ATTEMPTS = 3

// Bumped by every write, so a fetch can tell its answer is older than
// the list it would overwrite.
const state = () => ({ generation: {} })

const updateContext = {
  updateTimeout: null,
  promiseResolve: null,
  lastUpdatedValues: null,
}

const mutations = {
  BUMP_GENERATION(state, { application }) {
    state.generation = {
      ...state.generation,
      [application.id]: (state.generation[application.id] || 0) + 1,
    }
  },
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
    commit('BUMP_GENERATION', { application })
  },
  forceUpdate({ commit }, { application, integration, values }) {
    commit('UPDATE_ITEM', { application, integration, values })
    commit('BUMP_GENERATION', { application })
  },
  forceDelete({ commit, getters }, { application, integrationId }) {
    commit('DELETE_ITEM', { application, integrationId })
    commit('BUMP_GENERATION', { application })
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
    commit('BUMP_GENERATION', { application })
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
      const { data: updatedIntegration } = await IntegrationService(
        $client
      ).update(integration.id, values)
      // Only the response carries the updated `has_*` credential flags.
      await dispatch('forceUpdate', {
        application,
        integration,
        values: updatedIntegration,
      })
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
  async fetch({ commit, state, rootGetters }, { application }) {
    const { $client } = this
    const applicationId = application.id

    for (let attempt = 0; attempt < FETCH_ATTEMPTS; attempt++) {
      const before = state.generation[applicationId] || 0

      const { data: integrations } =
        await IntegrationService($client).fetchAll(applicationId)

      // Changed while this was open, so the answer is older than the list and
      // writing it would lose the change. Asked again rather than discarded:
      // most callers await this and then mark the application loaded, and
      // would keep an empty list until a reload.
      if ((state.generation[applicationId] || 0) !== before) {
        continue
      }

      // `forceSetAll` can have replaced the object this started with, and
      // filling that one leaves the one on screen empty.
      const current =
        rootGetters['application/get'](applicationId) || application

      // Committed rather than dispatched through `forceCreate`: writing the
      // answer is not a change to back off from, and a bump here would make
      // the next attempt back off from this one.
      commit('CLEAR_ITEMS', { application: current })
      integrations.forEach((integration) =>
        commit('ADD_ITEM', { application: current, integration })
      )

      return integrations
    }

    // Still moving. Null rather than a list older than the screen, so a
    // caller does not remember a load that did not happen.
    return null
  },
  /**
   * Loads the workspace integrations the application can use, at most once per
   * workspace: realtime events keep them current after that. Nothing is loaded
   * when the user can't list them, like a user with a role on some
   * applications only, or isn't a member of the workspace, like the one of a
   * template preview.
   *
   * @param {Object} application An application of the workspace.
   * @returns {Promise<Array|null>} The workspace integrations, or null when
   *   their list changed under the fetch and it gave up, like `fetch`.
   */
  async fetchWorkspaceIntegrationsOnce(
    { dispatch, getters, rootGetters },
    { application }
  ) {
    const workspace =
      application.workspace &&
      rootGetters['workspace/get'](application.workspace.id)
    if (
      !workspace ||
      !this.app.$hasPermission(
        'workspace.list_integrations',
        workspace,
        workspace.id
      )
    ) {
      return []
    }

    const sharedApplication = await dispatch(
      'application/fetchSharedApplication',
      workspace,
      { root: true }
    )
    if (!sharedApplication) {
      return []
    }
    if (sharedApplication._integrationsLoadedOnce) {
      return getters.getIntegrations(sharedApplication)
    }

    const integrations = await dispatch('fetch', {
      application: sharedApplication,
    })
    // Left unmarked, so the next application that asks fetches again.
    if (integrations === null) {
      return null
    }
    // `forceSetAll` can have replaced the object while the fetch was open.
    const current = rootGetters['application/get'](sharedApplication.id)
    if (current) {
      await dispatch(
        'application/forceUpdate',
        { application: current, data: { _integrationsLoadedOnce: true } },
        { root: true }
      )
    }
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
  /**
   * The integrations the application owns. A settings page lists these, while a
   * picker offers `getUsableIntegrations`.
   */
  getIntegrations: (state) => (application) => {
    return application?.integrations || []
  },
  /**
   * The integrations of the application's workspace, which every application of
   * the workspace can use. Empty for the shared application itself, which owns
   * them, and until `fetchWorkspaceIntegrationsOnce` loaded them.
   */
  getWorkspaceIntegrations:
    (state, getters, rootState, rootGetters) => (application) => {
      if (!application?.workspace) {
        return []
      }
      const sharedApplication = rootGetters['application/getSharedApplication'](
        application.workspace
      )
      if (!sharedApplication || sharedApplication.id === application.id) {
        return []
      }
      return getters.getIntegrations(sharedApplication)
    },
  /**
   * The integrations the application can use: its own, then the workspace ones.
   * Their `application_id` tells them apart.
   */
  getUsableIntegrations: (state, getters) => (application) => {
    return [
      ...getters.getIntegrations(application),
      ...getters.getWorkspaceIntegrations(application),
    ]
  },
  /**
   * A number that changes with every change to the integrations of the
   * application, so a component listing them knows when to refresh.
   */
  getGeneration: (state) => (application) => {
    return state.generation[application.id] || 0
  },
  /**
   * One of the integrations the application can use, its own or a workspace
   * one, so a service using a workspace integration finds it too.
   */
  getIntegrationById: (state, getters) => (application, id) => {
    return getters
      .getUsableIntegrations(application)
      .find((integration) => integration.id === id)
  },
}

export default {
  namespaced: true,
  state,
  getters,
  actions,
  mutations,
}
