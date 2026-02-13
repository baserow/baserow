import UserSourceService from '@baserow/modules/core/services/userSource'
import _ from 'lodash'

const state = {}

const updateContext = {
  updateTimeout: null,
  promiseResolve: null,
  lastUpdatedValues: null,
}

const mutations = {
  ADD_ITEM(state, { application, userSource, beforeId = null }) {
    if (beforeId === null) {
      application.user_sources.push(userSource)
    } else {
      const insertionIndex = application.user_sources.findIndex(
        (e) => e.id === beforeId
      )
      application.user_sources.splice(insertionIndex, 0, userSource)
    }
  },
  UPDATE_ITEM(state, { application, userSource: userSourceToUpdate, values }) {
    application.user_sources.forEach((userSource) => {
      if (userSource.id === userSourceToUpdate.id) {
        Object.assign(userSource, values)
      }
    })
  },
  DELETE_ITEM(state, { application, userSourceId }) {
    const index = application.user_sources.findIndex(
      (userSource) => userSource.id === userSourceId
    )
    if (index > -1) {
      application.user_sources.splice(index, 1)
    }
  },
  MOVE_ITEM(state, { application, index, oldIndex }) {
    application.user_sources.splice(
      index,
      0,
      application.user_sources.splice(oldIndex, 1)[0]
    )
  },
  CLEAR_ITEMS(state, { application }) {
    application.user_sources = []
  },
}

const actions = {
  forceCreate({ commit }, { application, userSource, beforeId = null }) {
    commit('ADD_ITEM', { application, userSource, beforeId })
  },
  forceUpdate({ commit }, { application, userSource, values }) {
    commit('UPDATE_ITEM', { application, userSource, values })
  },
  forceDelete({ commit }, { application, userSourceId }) {
    commit('DELETE_ITEM', { application, userSourceId })
  },
  forceMove(
    { commit, getters },
    { application, userSourceId, beforeUserSourceId }
  ) {
    const currentOrder = getters
      .getUserSources(application)
      .map((userSource) => userSource.id)
    const oldIndex = currentOrder.findIndex((id) => id === userSourceId)
    const index = beforeUserSourceId
      ? currentOrder.findIndex((id) => id === beforeUserSourceId)
      : getters.getUserSources(application).length

    // If the userSource is before the beforeUserSource we must decrease the target index by
    // one to compensate the removed userSource.
    if (oldIndex < index) {
      commit('MOVE_ITEM', { application, index: index - 1, oldIndex })
    } else {
      commit('MOVE_ITEM', { application, index, oldIndex })
    }
  },
  async create(
    { dispatch },
    { application, userSourceType, values, beforeId = null }
  ) {
    const { $registry, $i18n, $client, $config } = this
    const { data: userSource } = await UserSourceService($client).create(
      application.id,
      userSourceType,
      values,
      beforeId
    )

    await dispatch('forceCreate', { application, userSource, beforeId })

    return userSource
  },
  async update({ dispatch, getters }, { application, userSourceId, values }) {
    const { $registry, $i18n, $client, $config } = this
    const userSourcesOfPage = getters.getUserSources(application)
    const userSource = userSourcesOfPage.find(({ id }) => id === userSourceId)

    const oldValues = {}
    const newValues = {}

    Object.keys(values).forEach((name) => {
      if (!_.isEqual(userSource[name], values[name])) {
        oldValues[name] = userSource[name]
        newValues[name] = values[name]
      }
    })

    await dispatch('forceUpdate', {
      application,
      userSource,
      values: newValues,
    })

    try {
      const { data: newUserSource } = await UserSourceService($client).update(
        userSource.id,
        newValues
      )
      await dispatch('forceUpdate', {
        application,
        userSource,
        values: newUserSource,
      })
    } catch (error) {
      await dispatch('forceUpdate', {
        application,
        userSource,
        values: oldValues,
      })
      throw error
    }
  },

  async debouncedUpdate(
    { dispatch, getters },
    { application, userSourceId, values }
  ) {
    const { $registry, $i18n, $client, $config } = this
    const userSource = getters
      .getUserSources(application)
      .find(({ id }) => id === userSourceId)
    const oldValues = {}
    const newValues = {}
    Object.keys(values).forEach((name) => {
      if (Object.prototype.hasOwnProperty.call(userSource, name)) {
        oldValues[name] = userSource[name]
        newValues[name] = values[name]
      }
    })

    await dispatch('forceUpdate', {
      application,
      userSource,
      values: newValues,
    })

    return new Promise((resolve, reject) => {
      const fire = async () => {
        try {
          await UserSourceService($client).update(userSource.id, values)
          updateContext.lastUpdatedValues = values
          resolve()
        } catch (error) {
          // Revert to old values on error
          await dispatch('forceUpdate', {
            application,
            userSource,
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
  async delete({ dispatch, getters }, { application, userSourceId }) {
    const { $registry, $i18n, $client, $config } = this
    const userSourcesOfPage = getters.getUserSources(application)
    const userSourceIndex = userSourcesOfPage.findIndex(
      (userSource) => userSource.id === userSourceId
    )
    const userSourceToDelete = userSourcesOfPage[userSourceIndex]
    const beforeId =
      userSourceIndex !== userSourcesOfPage.length - 1
        ? userSourcesOfPage[userSourceIndex + 1].id
        : null

    await dispatch('forceDelete', { application, userSourceId })

    try {
      await UserSourceService($client).delete(userSourceId)
    } catch (error) {
      await dispatch('forceCreate', {
        application,
        userSource: userSourceToDelete,
        beforeId,
      })
      throw error
    }
  },
  async fetch({ dispatch, commit }, { application }) {
    const { $registry, $i18n, $client, $config } = this
    const { data: userSources } = await UserSourceService($client).fetchAll(
      application.id
    )

    commit('CLEAR_ITEMS', { application })
    await Promise.all(
      userSources.map((userSource) =>
        dispatch('forceCreate', { application, userSource })
      )
    )

    return userSources
  },

  async move({ dispatch }, { application, userSourceId, beforeUserSourceId }) {
    const { $registry, $i18n, $client, $config } = this
    await dispatch('forceMove', {
      application,
      userSourceId,
      beforeUserSourceId,
    })

    try {
      await UserSourceService($client).move(userSourceId, beforeUserSourceId)
    } catch (error) {
      await dispatch('forceMove', {
        application,
        userSourceId: beforeUserSourceId,
        beforeUserSourceId: userSourceId,
      })
      throw error
    }
  },
  async duplicate({ getters, dispatch }, { application, userSourceId }) {
    const userSource = getters
      .getUserSources(application)
      .find((e) => e.id === userSourceId)
    await dispatch('create', {
      application,
      userSourceType: userSource.type,
      beforeId: userSource.id,
    })
  },
}

const getters = {
  getUserSources: (state) => (application) => {
    return application.user_sources
  },
  getUserSourceById: (state) => (application, userSourceId) => {
    return application.user_sources.find(({ id }) => id === userSourceId)
  },
  getUserSourceByUId: (state) => (application, userSourceUId) => {
    return application.user_sources.find(({ uid }) => uid === userSourceUId)
  },
}

export default {
  namespaced: true,
  state,
  getters,
  actions,
  mutations,
}
