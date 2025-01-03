import ThemeService from '@baserow/modules/builder/services/theme'
import FontService from '@baserow/modules/builder/services/font'
import { clone } from '@baserow/modules/core/utils/object'

const state = {
  fonts: []
}

let patchRequestTimeout = null
let patchRequestResolve = null
let patchRequestProperties = {}
let patchRequestOldProperties = {}

const mutations = {
  UPDATE_PROPERTY(state, { builder, key, value }) {
    builder.theme[key] = value
  },

  SET_ITEMS(state, { fonts }) {
    state.fonts = fonts
  },
}

const actions = {
  /**
   * Immediately updates the provided property, but debounces for 1000ms before
   * making the request to the backend to update it.
   */
  setProperty({ commit }, { builder, key, value }) {
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
          await ThemeService(this.$client).update(builder.id, properties)
          resolve()
        } catch (error) {
          Object.keys(oldProperties).forEach((key) => {
            commit('UPDATE_PROPERTY', {
              builder,
              key,
              value: oldProperties[key],
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
      commit('UPDATE_PROPERTY', { builder, key, value })
    })
  },
  /**
   * Immediately updates the provided property, but it will not make a request to
   * the backend. This is used to visually update an invalid value, or for real-time
   * collaboration.
   */
  forceSetProperty({ commit }, { builder, key, value }) {
    commit('UPDATE_PROPERTY', { builder, key, value })
  },

  async fetchFonts({ commit }) {
    try {
      const resp = await FontService(this.$client).fetchFonts()
      commit('SET_ITEMS', { fonts: resp.data })
    } catch (e) {
      throw e
    }
  }
}

const getters = {
  getFonts: (state) => () => {
    return state.fonts
  }
}

export default {
  namespaced: true,
  state,
  getters,
  actions,
  mutations,
}
