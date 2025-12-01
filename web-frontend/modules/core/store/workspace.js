import { StoreItemLookupError } from '@baserow/modules/core/errors'
import WorkspaceService from '@baserow/modules/core/services/workspace'
import {
  setWorkspaceCookie,
  unsetWorkspaceCookie,
} from '@baserow/modules/core/utils/workspace'
import { CORE_ACTION_SCOPES } from '@baserow/modules/core/utils/undoRedoConstants'
import PermissionsService from '@baserow/modules/core/services/permissions'
import RolesService from '@baserow/modules/core/services/roles'

export function populateWorkspace(workspace) {
  workspace._ = {
    loading: false,
    selected: false,
    additionalLoading: false,
    permissionsLoaded: false,
    permissions: null,
    rolesLoaded: false,
    roles: null,
  }
  return workspace
}

const appendRoleTranslations = (roles, registry) => {
  const translationMap = Object.values(
    registry.getAll('permissionManager')
  ).reduce(
    (translations, manager) => ({
      ...translations,
      ...manager.getRolesTranslations(),
    }),
    {}
  )
  return roles.map((role) => {
    if (translationMap[role.uid]) {
      const { uid, ...rest } = role
      return {
        uid,
        description: translationMap[role.uid].description,
        name: translationMap[role.uid].name,
        ...rest,
      }
    }
    return role
  })
}

export const state = () => ({
  loaded: false,
  loading: false,
  items: [],
  selected: {},
  userIdsInSelected: new Set(),
})

export const mutations = {
  SET_LOADED(state, loaded) {
    state.loaded = loaded
  },
  SET_LOADING(state, loading) {
    state.loading = loading
  },
  SET_ITEMS(state, items) {
    // Set some default values that we might need later.
    state.items = items.map((item) => {
      item = populateWorkspace(item)
      return item
    })
  },
  SET_ITEM_LOADING(state, { workspace, value }) {
    if (!Object.prototype.hasOwnProperty.call(workspace, '_')) {
      return
    }
    workspace._.loading = value
  },
  SET_ITEM_ADDITIONAL_LOADING(state, { workspace, value }) {
    if (!Object.prototype.hasOwnProperty.call(workspace, '_')) {
      return
    }
    workspace._.additionalLoading = value
  },
  ADD_ITEM(state, item) {
    item = populateWorkspace(item)
    state.items.push(item)
  },
  UPDATE_ITEM(state, { id, values }) {
    const index = state.items.findIndex((item) => item.id === id)
    Object.assign(state.items[index], state.items[index], values)
  },
  ORDER_ITEMS(state, order) {
    state.items.forEach((workspace) => {
      const index = order.findIndex((value) => value === workspace.id)
      workspace.order = index === -1 ? 0 : index + 1
    })
  },
  DELETE_ITEM(state, id) {
    const index = state.items.findIndex((item) => item.id === id)
    state.items.splice(index, 1)
  },
  SET_SELECTED(state, workspace) {
    Object.values(state.items).forEach((item) => {
      item._.selected = false
    })
    workspace._.selected = true
    state.selected = workspace
    state.userIdsInSelected = new Set(workspace.users?.map((u) => u.user_id))
  },
  UNSELECT(state) {
    Object.values(state.items).forEach((item) => {
      item._.selected = false
    })
    state.selected = {}
  },
  ADD_WORKSPACE_USER(state, { workspaceId, values }) {
    const workspaceIndex = state.items.findIndex(
      (item) => item.id === workspaceId
    )
    if (workspaceIndex !== -1) {
      state.items[workspaceIndex].users.push(values)
      state.userIdsInSelected.add(values.user_id)
    }
  },
  UPDATE_WORKSPACE_USER(state, { workspaceId, id, values }) {
    const workspaceIndex = state.items.findIndex(
      (item) => item.id === workspaceId
    )
    if (workspaceIndex === -1) {
      return
    }
    const usersIndex = state.items[workspaceIndex].users.findIndex(
      (item) => item.id === id
    )
    if (usersIndex === -1) {
      return
    }
    Object.assign(
      state.items[workspaceIndex].users[usersIndex],
      state.items[workspaceIndex].users[usersIndex],
      values
    )
  },
  DELETE_WORKSPACE_USER(state, { workspaceId, id }) {
    const workspaceIndex = state.items.findIndex(
      (item) => item.id === workspaceId
    )
    if (workspaceIndex === -1) {
      return
    }
    const usersIndex = state.items[workspaceIndex].users.findIndex(
      (item) => item.id === id
    )
    if (usersIndex === -1) {
      return
    }
    const user = state.items[workspaceIndex].users[usersIndex]
    state.userIdsInSelected.delete(user.user_id)
    state.items[workspaceIndex].users.splice(usersIndex, 1)
  },
  SET_PERMISSIONS(state, { workspaceId, permissions }) {
    const workspaceIndex = state.items.findIndex(
      (item) => item.id === workspaceId
    )
    if (workspaceIndex === -1) {
      return
    }
    state.items[workspaceIndex]._.permissions = permissions
    state.items[workspaceIndex]._.permissionsLoaded = true
  },
  SET_ROLES(state, { workspaceId, roles }) {
    const workspaceIndex = state.items.findIndex(
      (item) => item.id === workspaceId
    )
    if (workspaceIndex === -1) {
      return
    }
    state.items[workspaceIndex]._.roles = roles
    state.items[workspaceIndex]._.rolesLoaded = true
  },
}

export const actions = {
  /**
   * If not already loading or loaded it will trigger the fetchAll action which
   * will load all the workspaces for the user.
   */
  async loadAll({ state, dispatch }) {
    if (!state.loaded && !state.loading) {
      await dispatch('fetchAll')
    }
  },
  /**
   * Clears all the selected workspaces. Can be used when logging off.
   */
  clearAll({ commit, dispatch }) {
    commit('SET_ITEMS', [])
    commit('UNSELECT')
    commit('SET_LOADED', false)
    return dispatch('application/clearAll', undefined, { root: true })
  },
  /**
   * Changes the loading state of a specific workspace.
   */
  setItemLoading({ commit }, { workspace, value }) {
    commit('SET_ITEM_LOADING', { workspace, value })
  },
  /**
   * Fetches all the workspaces of an authenticated user.
   */
  async fetchAll({ commit, dispatch, state }) {
    commit('SET_LOADING', true)

    try {
      const { data } = await WorkspaceService(this.$client).fetchAll()
      commit('SET_LOADED', true)
      commit('SET_ITEMS', data)
    } catch {
      commit('SET_ITEMS', [])
    }
    commit('SET_LOADING', false)

    if (state.items.length > 0) {
      // Every workspace contains an unread notifications count for the user,
      // so let's update that.
      dispatch(
        'notification/setPerWorkspaceUnreadCount',
        { workspaces: state.items },
        { root: true }
      )
    }
  },
  /**
   * Creates a new workspace with the given values.
   */
  async create({ commit, dispatch }, values) {
    const { data } = await WorkspaceService(this.$client).create(values)
    dispatch('forceCreate', data)
    return data
  },
  /**
   * Forcefully create an item in the store without making a call to the server.
   */
  forceCreate({ commit }, values) {
    commit('ADD_ITEM', values)
  },
  /**
   * Updates the values of the workspace with the provided id.
   */
  async update({ commit, dispatch }, { workspace, values }) {
    const { data } = await WorkspaceService(this.$client).update(
      workspace.id,
      values
    )
    // Create a dict with only the values we want to update.
    const update = Object.keys(values).reduce((result, key) => {
      result[key] = data[key]
      return result
    }, {})
    dispatch('forceUpdate', { workspace, values: update })
  },
  /**
   * Forcefully update the item in the store without making a call to the server.
   */
  forceUpdate({ commit }, { workspace, values }) {
    commit('UPDATE_ITEM', { id: workspace.id, values })
  },
  /**
   * Forcefully reorders the items in the store without making a call to the server.
   */
  forceOrder({ commit }, order) {
    commit('ORDER_ITEMS', order)
  },
  /**
   * Updates the order of the workspaces for the current user.
   */
  async order({ commit, getters }, { order, oldOrder }) {
    commit('ORDER_ITEMS', order)

    try {
      await WorkspaceService(this.$client).order(order)
    } catch (error) {
      commit('ORDER_ITEMS', oldOrder)
      throw error
    }
  },
  /**
   * Makes the current authenticated user leave the workspace.
   */
  async leave({ commit, dispatch }, workspace) {
    await WorkspaceService(this.$client).leave(workspace.id)
    await dispatch('forceDelete', workspace)
  },
  /**
   * Deletes an existing workspace with the provided id.
   */
  async delete({ commit, dispatch }, workspace) {
    try {
      await WorkspaceService(this.$client).delete(workspace.id)
      await dispatch('forceDelete', workspace)
    } catch (error) {
      // If the workspace to delete wasn't found we can just delete it from the
      // state.
      if (error.response && error.response.status === 404) {
        await dispatch('forceDelete', workspace)
      } else {
        throw error
      }
    }
  },
  /**
   * Forcefully remove the workspace from the items  without calling the server. The
   * delete event is also called for all the applications that are in the
   * workspace. This is needed so that we can redirect the user to another page if for
   * example a Table is open that has been deleted because the workspace has been deleted.
   */
  async forceDelete({ commit, dispatch, rootGetters }, workspace) {
    dispatch('job/deleteForWorkspace', workspace, { root: true })
    this.$bus.$emit('workspace-deleted', { workspace })
    const applications = rootGetters['application/getAllOfWorkspace'](workspace)
    applications.forEach((application) => {
      return dispatch('application/forceDelete', application, { root: true })
    })

    if (workspace._.selected) {
      // Navigate to the dashboard if selected because any of those related pages
      // can't be accessed anymore.
      await dispatch('unselect', workspace)
      await this.$router.push({ name: 'dashboard' })
    }

    commit('DELETE_ITEM', workspace.id)
  },
  async forceFetchPermissions({ commit }, workspace) {
    const { data } = await PermissionsService(this.$client).get(workspace)
    commit('SET_PERMISSIONS', {
      workspaceId: workspace.id,
      permissions: data,
    })
  },
  async fetchPermissions({ commit, dispatch }, workspace) {
    // The permissions only have to be loaded once.
    if (workspace._.permissionsLoaded) {
      return
    }

    commit('SET_ITEM_ADDITIONAL_LOADING', { workspace, value: true })
    try {
      await dispatch('forceFetchPermissions', workspace)
    } finally {
      commit('SET_ITEM_ADDITIONAL_LOADING', { workspace, value: false })
    }
  },
  async fetchRoles({ dispatch }, workspace) {
    if (!workspace._.rolesLoaded) {
      await dispatch('forceRefreshRoles', workspace)
    }
  },
  async forceRefreshRoles({ commit, getters }, workspace) {
    commit('SET_ITEM_ADDITIONAL_LOADING', { workspace, value: true })

    try {
      const { data } = await RolesService(
        this.$client,
        this.app.$hasFeature,
        this.$registry
      ).get(workspace)
      const translatedRoles = appendRoleTranslations(data, this.app.$registry)
      commit('SET_ROLES', { workspaceId: workspace.id, roles: translatedRoles })
    } finally {
      commit('SET_ITEM_ADDITIONAL_LOADING', { workspace, value: false })
    }
  },
  /**
   * Select a workspace and fetch all the applications related to that workspace.
   */
  async select({ commit, dispatch }, workspace) {
    await dispatch('fetchPermissions', workspace)
    await dispatch('fetchRoles', workspace)
    commit('SET_SELECTED', workspace)
    setWorkspaceCookie(workspace.id, this.app)
    dispatch(
      'undoRedo/updateCurrentScopeSet',
      CORE_ACTION_SCOPES.workspace(workspace.id),
      {
        root: true,
      }
    )
    dispatch('notification/setWorkspace', { workspace }, { root: true })
    return workspace
  },
  /**
   * Select a workspace by a given workspace id.
   */
  selectById({ dispatch, getters }, id) {
    const workspace = getters.get(id)
    if (workspace === undefined) {
      throw new StoreItemLookupError(`Workspace with id ${id} is not found.`)
    }
    return dispatch('select', workspace)
  },
  /**
   * Unselect a workspace if selected and clears all the fetched applications.
   */
  unselect({ commit, dispatch, getters }, workspace) {
    commit('UNSELECT', {})
    unsetWorkspaceCookie(this.app)
    dispatch(
      'undoRedo/updateCurrentScopeSet',
      CORE_ACTION_SCOPES.workspace(null),
      {
        root: true,
      }
    )
    return dispatch('application/clearAll', workspace, { root: true })
  },
  /**
   * Forcefully adds a workspace user in the list of workspace's users.
   */
  forceAddWorkspaceUser({ commit }, { workspaceId, values }) {
    commit('ADD_WORKSPACE_USER', { workspaceId, values })
  },
  /**
   * Forcefully updates a workspace user in the list of workspace's users
   * and updates workspace's permissions attr if the workspace user is the
   * same as the current user.
   */
  forceUpdateWorkspaceUser(
    { commit, rootGetters },
    { workspaceId, id, values }
  ) {
    commit('UPDATE_WORKSPACE_USER', { workspaceId, id, values })
    const userId = rootGetters['auth/getUserId']
    if (values.user_id === userId) {
      commit('UPDATE_ITEM', {
        id: workspaceId,
        values: { permissions: values.permissions },
      })
    }
  },
  /**
   * Forcefully updates user's properties based on userId across all workspace users
   * of all workspaces. Can be used e.g. to change the user's name across all workspace
   * users that represent the same user in the system.
   */
  forceUpdateWorkspaceUserAttributes(
    { commit, rootGetters },
    { userId, values }
  ) {
    const workspaces = rootGetters['workspace/getAll']
    for (const workspace of workspaces) {
      const usersIndex = workspace.users.findIndex(
        (item) => item.user_id === userId
      )
      if (usersIndex !== -1) {
        commit('UPDATE_WORKSPACE_USER', {
          workspaceId: workspace.id,
          id: workspace.users[usersIndex].id,
          values,
        })
      }
    }
  },
  /**
   * Forcefully deletes a workspace user in the list of workspace's users. If the
   * workspace user is the current user, the whole workspace is removed.
   */
  forceDeleteWorkspaceUser(
    { commit, rootGetters },
    { workspaceId, id, values }
  ) {
    const userId = rootGetters['auth/getUserId']
    if (values.user_id === userId) {
      commit('DELETE_ITEM', { id: workspaceId })
    } else {
      commit('DELETE_WORKSPACE_USER', { workspaceId, id })
    }
  },
  /**
   * Forcefully deletes a user by deleting various user workspace instances
   * in all workspaces where the user is present.
   */
  forceDeleteUser({ commit, rootGetters }, { userId }) {
    const workspaces = rootGetters['workspace/getAll']
    for (const workspace of workspaces) {
      const usersIndex = workspace.users.findIndex(
        (item) => item.user_id === userId
      )
      if (usersIndex !== -1) {
        commit('DELETE_WORKSPACE_USER', {
          workspaceId: workspace.id,
          id: workspace.users[usersIndex].id,
        })
      }
    }
  },
}

export const getters = {
  isLoaded(state) {
    return state.loaded
  },
  isLoading(state) {
    return state.loading
  },
  get: (state) => (id) => {
    return state.items.find((item) => item.id === id)
  },
  getAll(state) {
    return state.items
  },
  getAllSorted(state) {
    return state.items.map((g) => g).sort((a, b) => a.order - b.order)
  },
  /**
   * Never use this value in any component to get the current workspace. This is
   * just used for visual purposes in the left sidebar.
   */
  getSelected(state) {
    return state.selected
  },
  selectedId(state) {
    if (!Object.prototype.hasOwnProperty.call(state.selected, 'id')) {
      throw new Error('There is no selected workspace.')
    }

    return state.selected.id
  },
  selectedWorkspace(state) {
    if (!Object.prototype.hasOwnProperty.call(state.selected, 'id')) {
      throw new Error('There is no selected workspace.')
    }

    return state.selected
  },
  isUserIdMemberOfSelectedWorkspace: (state) => (userId) => {
    return state.userIdsInSelected.has(parseInt(userId))
  },
  getAllUsers(state) {
    const users = {}
    for (const workspace of state.items) {
      for (const user of workspace.users) {
        users[user.user_id] = user
      }
    }
    return users
  },
  getAllUsersByEmail(state) {
    const users = {}
    for (const workspace of state.items) {
      for (const user of workspace.users) {
        users[user.email] = user
      }
    }
    return users
  },
  getAllUsersByName(state) {
    const users = {}
    for (const workspace of state.items) {
      for (const user of workspace.users) {
        users[user.name] = user
      }
    }
    return users
  },
  getUserById: (state, getters) => (userId) => {
    const users = getters.getAllUsers
    return users[userId]
  },
  getUserByEmail: (state, getters) => (email) => {
    const users = getters.getAllUsersByEmail
    return users[email]
  },
  getUserByName: (state, getters) => (name) => {
    const users = getters.getAllUsersByName
    return users[name]
  },
  haveWorkspacePermissionsBeenLoaded: (state, getters) => (workspaceId) => {
    return getters.get(workspaceId)._.permissionsLoaded
  },
  getAllPermissions: (state, getters) => (workspaceId) => {
    const workspace = getters.get(workspaceId)
    if (!workspace) {
      return null
    }
    return workspace._.permissions
  },
}

export default {
  namespaced: true,
  state,
  getters,
  actions,
  mutations,
}
