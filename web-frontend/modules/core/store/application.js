import { StoreItemLookupError } from '@baserow/modules/core/errors'
import ApplicationService from '@baserow/modules/core/services/application'
import { clone } from '@baserow/modules/core/utils/object'
import { CORE_ACTION_SCOPES } from '@baserow/modules/core/utils/undoRedoConstants'
import { generateHash } from '@baserow/modules/core/utils/hashing'

export function populateApplication(application, registry) {
  const type = registry.get('application', application.type)

  const app = {
    ...application,
    _: {
      type: type.serialize(),
      loading: false,
      selected: false,
    },
  }
  return type.populate(app)
}

export const state = () => ({
  loading: false,
  loaded: false,
  items: [],
  selected: null,
})

export const mutations = {
  SET_ITEMS(state, applications) {
    state.items = applications
  },
  SET_LOADING(state, value) {
    state.loading = value
  },
  SET_LOADED(state, value) {
    state.loaded = value
  },
  SET_ITEM_LOADING(state, { application, value }) {
    application._.loading = value
  },
  ADD_ITEM(state, item) {
    state.items.push(item)
  },
  APPEND_ITEMS(state, items) {
    state.items = state.items.concat(items)
  },
  UPDATE_ITEM(state, { id, values }) {
    const index = state.items.findIndex((item) => item.id === id)
    if (index !== -1) {
      Object.assign(state.items[index], state.items[index], values)
    }
  },
  ORDER_ITEMS(state, { workspace, order, isHashed = false }) {
    state.items
      .filter((item) => item.workspace.id === workspace.id)
      .forEach((item) => {
        const itemId = isHashed ? generateHash(item.id) : item.id
        const index = order.findIndex((value) => value === itemId)
        item.order = index === -1 ? undefined : index + 1
      })
  },
  DELETE_ITEM(state, id) {
    const index = state.items.findIndex((item) => item.id === id)
    if (index !== -1) {
      state.items.splice(index, 1)
    }
  },
  DELETE_ITEMS_FOR_WORKSPACE(state, workspaceId) {
    state.items = state.items.filter((app) => app.workspace.id !== workspaceId)
  },
  SET_SELECTED(state, application) {
    Object.values(state.items).forEach((item) => {
      item._.selected = false
    })
    application._.selected = true
    state.selected = application
  },
  UNSELECT(state) {
    Object.values(state.items).forEach((item) => {
      item._.selected = false
    })
    state.selected = {}
  },
  CLEAR_CHILDREN_SELECTED(state, { type, application }) {
    type.clearChildrenSelected(application)
  },
}

export const actions = {
  /**
   * Changes the loading state of a specific item.
   */
  setItemLoading({ commit }, { application, value }) {
    commit('SET_ITEM_LOADING', { application, value })
  },
  /**
   * Force creates a list of applications.
   */
  forceCreateAll({ dispatch }, applications) {
    applications.forEach((app) => {
      dispatch('forceCreate', app)
    })
  },
  /**
   * Fetches all the applications for the authenticated user.
   */
  async fetchAll({ commit, dispatch }) {
    commit('SET_LOADING', true)

    try {
      const { data } = await ApplicationService(this.$client).fetchAll()
      await dispatch('forceSetAll', { applications: data })
    } catch (error) {
      commit('SET_ITEMS', [])
      commit('SET_LOADING', false)

      throw error
    }
  },
  forceSetAll({ commit }, { applications }) {
    const apps = applications.map((application) =>
      populateApplication(application, this.$registry)
    )
    commit('SET_ITEMS', apps)
    commit('SET_LOADING', false)
    commit('SET_LOADED', true)
    return { applications: apps }
  },
  /**
   * Clears all the currently selected applications, this could be called when
   * the workspace is deleted of when the user logs off.
   */
  clearAll({ commit }, workspace) {
    commit('DELETE_ITEMS_FOR_WORKSPACE', workspace)
    commit('UNSELECT')
    commit('SET_LOADED', false)
  },
  /**
   * If called all the applications that are in the state will clear their
   * children active state if they have one.
   */
  clearChildrenSelected({ commit, getters }) {
    Object.values(getters.getAll).forEach((application) => {
      const type = this.$registry.get('application', application.type)
      commit('CLEAR_CHILDREN_SELECTED', { type, application })
    })
  },
  /**
   * Creates a new application with the given type and values for the currently
   * selected workspace.
   */
  async create({ dispatch }, { type, workspace, values, initWithData = true }) {
    if (Object.prototype.hasOwnProperty.call(values, 'type')) {
      throw new Error(
        'The key "type" is a reserved, but is already set on the ' +
          'values when creating a new application.'
      )
    }

    if (!this.$registry.exists('application', type)) {
      throw new StoreItemLookupError(
        `An application type with type "${type}" doesn't exist.`
      )
    }

    const postData = clone(values)
    postData.type = type
    postData.init_with_data = initWithData

    const { data } = await ApplicationService(this.$client).create(
      workspace.id,
      postData
    )
    return dispatch('forceCreate', data)
  },
  /**
   * Forcefully create an item in the store without making a call to the server.
   */
  forceCreate({ commit, state, getters }, data) {
    const app = populateApplication(data, this.$registry)
    const index = state.items.findIndex((item) => item.id === app.id)
    if (index === -1) {
      commit('ADD_ITEM', app)
    } else {
      commit('UPDATE_ITEM', { id: app.id, values: app })
    }
    return getters.get(app.id)
  },
  /**
   * Updates the values of an existing application.
   */
  async update({ dispatch }, { application, values }) {
    const { data } = await ApplicationService(this.$client).update(
      application.id,
      values
    )

    // Create a dict with only the values we want to update.
    const update = Object.keys(values).reduce((result, key) => {
      result[key] = data[key]
      return result
    }, {})

    dispatch('forceUpdate', { application, data: update })
  },
  /**
   * Forcefully update an item in the store without making a call to the server.
   */
  forceUpdate({ commit }, { application, data }) {
    const type = this.$registry.get('application', application.type)
    data = type.prepareForStoreUpdate(application, data)

    commit('UPDATE_ITEM', { id: application.id, values: data })
  },
  /**
   * Updates the order of all the applications in a workspace.
   */
  async order(
    { commit, getters },
    { workspace, order, oldOrder, isHashed = false }
  ) {
    commit('ORDER_ITEMS', { workspace, order, isHashed })

    try {
      await ApplicationService(this.$client).order(workspace.id, order)
    } catch (error) {
      commit('ORDER_ITEMS', { workspace, order: oldOrder, isHashed })
      throw error
    }
  },

  /**
   * Deletes an existing application.
   */
  async delete({ commit, dispatch, getters }, application) {
    try {
      await ApplicationService(this.$client).delete(application.id)
      dispatch('forceDelete', application)
    } catch (error) {
      if (error.response && error.response.status === 404) {
        dispatch('forceDelete', application)
      } else {
        throw error
      }
    }
  },
  /**
   * Forcefully delete an item in the store without making a call to the server.
   */
  forceDelete({ commit, dispatch }, application) {
    const type = this.$registry.get('application', application.type)
    dispatch('job/deleteForApplication', application, { root: true })
    type.delete(application, this)
    commit('DELETE_ITEM', application.id)
  },
  /**
   * Select an application.
   */
  select({ commit, dispatch }, application) {
    commit('SET_SELECTED', application)
    dispatch(
      'undoRedo/updateCurrentScopeSet',
      CORE_ACTION_SCOPES.application(application.id),
      {
        root: true,
      }
    )
    return application
  },
  /**
   * Select an application by a given application id.
   */
  selectById({ dispatch, getters }, id) {
    const application = getters.get(id)
    if (application === undefined) {
      throw new StoreItemLookupError(`Application with id ${id} is not found.`)
    }
    return dispatch('select', application)
  },
  /**
   * Unselect the application
   */
  unselect({ commit, dispatch }) {
    commit('UNSELECT', {})
    dispatch(
      'undoRedo/updateCurrentScopeSet',
      CORE_ACTION_SCOPES.application(null),
      {
        root: true,
      }
    )
  },
}

export const getters = {
  isLoading(state) {
    return state.loading
  },
  isLoaded(state) {
    return state.loaded
  },
  isSelected: (state) => (application) => {
    return state.selected?.id === application.id
  },
  get: (state) => (id) => {
    return state.items.find((item) => item.id === id)
  },
  getSelected: (state) => {
    return state.selected
  },
  getAll(state) {
    return state.items
  },
  getAllOfWorkspace: (state) => (workspace) => {
    return state.items.filter(
      (application) => application.workspace.id === workspace.id
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
