import ThemeService from '@baserow/modules/builder/services/theme'
import { clone } from '@baserow/modules/core/utils/object'

const state = {}

let patchRequestTimeout = null
let patchRequestResolve = null
let patchRequestProperties = {}
let patchRequestOldProperties = {}

const mutations = {
  UPDATE(state, { builder, values }) {
    Object.keys(values).forEach((key) => {
      builder.theme[key] = values[key]
    })
  },
}

const actions = {
  /**
   * Immediately updates the provided property, but debounces for 1000ms before
   * making the request to the backend to update it.
   */
  setProperty({ commit }, { builder, key, value }) {
    const { $registry, $i18n, $client, $config } = this
    return new Promise((resolve, reject) => {
      // Call the old resolve function because otherwise it can result in a memory leak.
      if (patchRequestResolve) {
        patchRequestResolve()
        patchRequestResolve = null
      }

      if (patchRequestTimeout) {
        clearTimeout(patchRequestTimeout)
      }

      const update = async () => {
        const oldProperties = clone(patchRequestOldProperties)
        const properties = clone(patchRequestProperties)

        patchRequestTimeout = null
        patchRequestOldProperties = {}
        patchRequestProperties = {}

        try {
          await ThemeService($client).update(builder.id, properties)
          resolve()
        } catch (error) {
          Object.keys(oldProperties).forEach((key) => {
            commit('UPDATE', {
              builder,
              values: { [key]: oldProperties[key] },
            })
          })
          reject(error)
        }
      }

      patchRequestTimeout = setTimeout(update, 1000)
      patchRequestResolve = resolve
      // Only set the old property if it wasn't set before because we want to be able
      // to reset to the initial value if the request fails.
      if (!patchRequestOldProperties[key]) {
        patchRequestOldProperties[key] = builder.theme[key]
      }
      patchRequestProperties[key] = value
      commit('UPDATE', { builder, values: { [key]: value } })
    })
  },
  /**
   * Immediately updates the provided values, but it will not make a request to
   * the backend. This is used to visually update multiple invalid values, or
   * for real-time collaboration.
   */
  forceUpdate({ commit }, { builder, values }) {
    commit('UPDATE', { builder, values })
  },
}

const getters = {}

export default {
  namespaced: true,
  state,
  getters,
  actions,
  mutations,
}
