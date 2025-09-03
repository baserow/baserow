import jwtDecode from 'jwt-decode'
import Vue from 'vue'
import _ from 'lodash'

import AuthService from '@baserow/modules/core/services/auth'
import WorkspaceService from '@baserow/modules/core/services/workspace'
import {
  setToken,
  setUserSessionCookie,
  unsetToken,
  unsetUserSessionCookie,
} from '@baserow/modules/core/utils/auth'
import { unsetWorkspaceCookie } from '@baserow/modules/core/utils/workspace'
import { v4 as uuidv4 } from 'uuid'

export const state = () => ({
  refreshing: false,
  token: null,
  refreshToken: null,
  tokenUpdatedAt: 0,
  tokenPayload: null,
  refreshTokenPayload: null,
  permissions: [],
  user: null,
  signedUserSession: null,
  authenticated: false,
  additional: {},
  webSocketId: null,
  // Indicates whether a token should be set persistently as a cookie using the
  // `setToken` function.
  preventSetToken: false,
  untrustedClientSessionId: uuidv4(),
  userSessionExpired: false,
  workspaceInvitations: [],
  umreadUserNotificationCount: 0,
})

export const mutations = {
  /* eslint-disable camelcase */
  SET_USER_DATA(
    state,
    {
      access_token,
      refresh_token,
      user_session,
      user,
      permissions,
      tokenUpdatedAt,
      ...additional
    }
  ) {
    state.token = access_token
    state.refreshToken = refresh_token
    state.tokenUpdatedAt = tokenUpdatedAt || new Date().getTime()
    state.signedUserSession = user_session
    state.tokenPayload = jwtDecode(state.token)
    if (state.refreshToken) {
      state.refreshTokenPayload = jwtDecode(state.refreshToken)
    }
    // Global permissions annotated on the User.
    state.permissions = permissions
    /* eslint-enable camelcase */
    state.user = user
    // Additional entries in the response payload could have been added via the
    // backend user data registry. We want to store them in the `additional` state so
    // that it can be used by other modules.
    state.additional = additional
    state.authenticated = true
    state.userSessionExpired = false
  },
  UPDATE_USER_DATA(state, { user, ...data }) {
    if (user !== undefined) {
      Object.assign(state.user, user)
    }
    // Deep merge using lodash customized to use Vue.set to maintain reactivity. Arrays
    // and other non pure object types will be overridden, objects will be merged.
    function customizer(objValue, srcValue, key, object) {
      Vue.set(object, key, srcValue)
    }
    _.mergeWith(state.additional, data, customizer)
  },
  SET_ADDITIONAL_DATA(state, additional) {
    state.additional = additional
  },
  LOGOFF(state) {
    state.token = null
    state.refreshToken = null
    state.tokenUpdatedAt = 0
    state.tokenPayload = null
    state.refreshTokenPayload = null
    state.authenticated = false
    state.permissions = []
  },
  CLEAR_USER_DATA(state) {
    state.token = null
    state.refreshToken = null
    state.tokenUpdatedAt = 0
    state.tokenPayload = null
    state.refreshTokenPayload = null
    state.user = null
    state.authenticated = false
    state.permissions = []
  },
  SET_REFRESHING(state, refreshing) {
    state.refreshing = refreshing
  },
  SET_WEB_SOCKET_ID(state, id) {
    state.webSocketId = id
  },
  SET_PREVENT_SET_TOKEN(state, value) {
    state.preventSetToken = value
  },
  SET_USER_SESSION_EXPIRED(state, expired) {
    state.userSessionExpired = expired
  },
  SET_WORKSPACE_INVIATIONS(state, invitations) {
    state.workspaceInvitations = invitations
  },
  ADD_OR_UPDATE_WORKSPACE_INVITATION(state, invitation) {
    const existingIndex = state.workspaceInvitations.findIndex(
      (c) => c.id === invitation.id
    )
    if (existingIndex !== -1) {
      state.workspaceInvitations.splice(existingIndex, 1, invitation)
    } else {
      state.workspaceInvitations.push(invitation)
    }
  },
  REMOVE_WORKSPACE_INVITATION(state, invitationId) {
    const existingIndex = state.workspaceInvitations.findIndex(
      (c) => c.id === invitationId
    )
    if (existingIndex !== -1) {
      state.workspaceInvitations.splice(existingIndex, 1)
    }
  },
}

export const actions = {
  /**
   * Authenticate a user by his email and password.
   */
  async login({ getters, dispatch }, { email, password }) {
    const { data } = await AuthService(this.$client).login(email, password)
    return dispatch('loginWithData', { data })
  },
  /**
   * Authenticate a user by data returned from an auth endpoint.
   * If successful, commit the token to the state and start the refresh
   * timeout to stay authenticated.
   */
  loginWithData({ getters, dispatch }, { data }) {
    if (data.user) {
      dispatch('setUserData', data)
      if (!getters.getPreventSetToken) {
        setToken(this.app, getters.refreshToken)
        setUserSessionCookie(this.app, getters.signedUserSession)
      }
      return data.user
    } else if (data.two_factor_auth) {
      return {
        two_factor_auth: data.two_factor_auth,
        token: data.token,
      }
    }
  },
  /**
   * Register a new user and immediately authenticate. If successful commit the
   * token to the state and start the refresh timeout to stay authenticated.
   */
  async register(
    { commit, dispatch },
    {
      email,
      name,
      password,
      language,
      workspaceInvitationToken = null,
      templateId = null,
    }
  ) {
    const { data } = await AuthService(this.$client).register(
      email,
      name,
      password,
      language,
      true,
      workspaceInvitationToken,
      templateId
    )

    if (data.refresh_token) {
      setToken(this.app, data.refresh_token)
      setUserSessionCookie(this.app, data.user_session)
      dispatch('setUserData', data)
    }
  },
  /**
   * Logs off the user by removing the token as a cookie and clearing the user
   * data.
   */
  logoff({ getters, dispatch }, { invalidateToken = false }) {
    const refreshToken = getters.refreshToken

    dispatch('forceLogoff')

    if (invalidateToken) {
      // Invalidate the token async because we don't have to wait for that.
      setTimeout(() => {
        AuthService(this.$client).blacklistToken(refreshToken)
      })
    }
  },
  forceLogoff({ commit }) {
    unsetToken(this.app)
    unsetUserSessionCookie(this.app)
    unsetWorkspaceCookie(this.app)
    commit('LOGOFF')
  },
  /**
   * Clears all the user data present in any other stores.
   */
  async clearAllStoreUserData({ commit, dispatch }) {
    await dispatch('workspace/clearAll', {}, { root: true })
    await dispatch('workspace/unselect', {}, { root: true })
    await dispatch('job/clearAll', {}, { root: true })
    await dispatch('notification/reset', {}, { root: true })
    commit('CLEAR_USER_DATA')
  },
  /**
   * Refresh the existing token. If successful commit the new token and start a
   * new refresh timeout. If unsuccessful the existing cookie and user data is
   * cleared.
   */
  async refresh({ commit, getters, dispatch }, token = null) {
    const refreshToken = token || getters.refreshToken
    if (!refreshToken) {
      throw new Error('Invalid refresh token')
    }

    try {
      const tokenUpdatedAt = new Date().getTime()
      const { data } = await AuthService(this.$client).refresh(refreshToken)
      // if ROTATE_REFRESH_TOKEN=False in the backend the response will not contain
      // a new refresh token. In that case, we keep the one we just used.
      dispatch('setUserData', {
        refresh_token: refreshToken,
        tokenUpdatedAt,
        ...data,
      })
      if (!getters.getPreventSetToken && data.refresh_token) {
        setToken(this.app, getters.refreshToken)
      }
    } catch (error) {
      if (error.response?.status === 401) {
        unsetToken(this.app)
        unsetUserSessionCookie(this.app)
        unsetWorkspaceCookie(this.app)
        if (getters.isAuthenticated) {
          dispatch('setUserSessionExpired', true)
        }
      }
      throw error
    }
  },
  /**
   * The web socket id is generated by the backend when connecting to the real time
   * updates web socket. This id will be added to each AJAX request so the backend
   * knows not to send any real time changes to the sender.
   */
  setWebSocketId({ commit }, webSocketId) {
    commit('SET_WEB_SOCKET_ID', webSocketId)
  },
  /**
   * Updates the account information is the authenticated user.
   */
  async update({ getters, commit, dispatch }, values) {
    const { data } = await AuthService(this.$client).update(values)
    dispatch('forceUpdateUserData', { user: data })
    dispatch(
      'workspace/forceUpdateWorkspaceUserAttributes',
      {
        userId: getters.getUserId,
        values: {
          name: data.first_name,
        },
      },
      {
        root: true,
      }
    )
    return data
  },
  forceUpdateUserData({ commit }, data) {
    commit('UPDATE_USER_DATA', data)
    this.app.$bus.$emit('user-data-updated', data)
  },
  setUserData({ commit, dispatch }, data) {
    commit('SET_USER_DATA', data)
    dispatch(
      'notification/setUserUnreadCount',
      { count: data.user_notifications?.unread_count },
      { root: true }
    )
  },
  forceSetUserData({ commit }, data) {
    commit('SET_USER_DATA', data)
  },
  forceSetAdditionalData({ commit }, data) {
    commit('SET_ADDITIONAL_DATA', data)
  },
  preventSetToken({ commit }) {
    commit('SET_PREVENT_SET_TOKEN', true)
  },
  setUserSessionExpired({ commit }, value) {
    unsetToken(this.app)
    unsetUserSessionCookie(this.app)
    unsetWorkspaceCookie(this.app)
    commit('SET_USER_SESSION_EXPIRED', value)
  },
  async fetchWorkspaceInvitations({ commit }) {
    const { data } = await AuthService(this.$client).dashboard()
    commit('SET_WORKSPACE_INVIATIONS', data.workspace_invitations)
    return data.workspace_invitations
  },
  forceUpdateOrCreateWorkspaceInvitation({ commit }, invitation) {
    commit('ADD_OR_UPDATE_WORKSPACE_INVITATION', invitation)
  },
  async acceptWorkspaceInvitation({ commit }, invitationId) {
    const { data: workspace } = await WorkspaceService(
      this.$client
    ).acceptInvitation(invitationId)
    commit('REMOVE_WORKSPACE_INVITATION', invitationId)
    return workspace
  },
  forceAcceptWorkspaceInvitation({ commit }, invitation) {
    commit('REMOVE_WORKSPACE_INVITATION', invitation.id)
  },
  async rejectWorkspaceInvitation({ commit }, invitationId) {
    await WorkspaceService(this.$client).rejectInvitation(invitationId)
    commit('REMOVE_WORKSPACE_INVITATION', invitationId)
  },
  forceRejectWorkspaceInvitation({ commit }, invitation) {
    commit('REMOVE_WORKSPACE_INVITATION', invitation.id)
  },
}

export const getters = {
  isAuthenticated(state) {
    return state.authenticated
  },
  isRefreshing(state) {
    return state.refreshing
  },
  token(state) {
    return state.token
  },
  refreshToken(state) {
    return state.refreshToken
  },
  refreshTokenPayload(state) {
    return state.refreshTokenPayload
  },
  signedUserSession(state) {
    return state.signedUserSession
  },
  webSocketId(state) {
    return state.webSocketId
  },
  getUserObject(state) {
    return state.user
  },
  getGlobalUserPermissions(state) {
    return state.permissions
  },
  getName(state) {
    return state.user ? state.user.first_name : ''
  },
  getUsername(state) {
    return state.user ? state.user.username : ''
  },
  getUserId(state) {
    return state.user ? state.user.id : null
  },
  getLanguage(state) {
    return state.user ? state.user.language : 'en'
  },
  isStaff(state) {
    return state.user ? state.user.is_staff : false
  },
  getCompletedGuidedTour(state) {
    return state?.user?.completed_guided_tours || []
  },
  getUntrustedClientSessionId(state) {
    return state.untrustedClientSessionId
  },
  shouldRefreshToken: (state) => () => {
    // the user must be authenticated to refresh the token
    if (!state.authenticated) {
      return false
    }

    const data = state.tokenPayload
    const now = new Date().getTime()
    const tokenLifespan = (data.exp - data.iat) * 1000
    return (now - state.tokenUpdatedAt) / tokenLifespan > 0.8
  },
  getAdditionalUserData(state) {
    return state.additional
  },
  getPreventSetToken(state) {
    return state.preventSetToken
  },
  isUserSessionExpired: (state) => {
    return state.userSessionExpired
  },
  getWorkspaceInvitations(state) {
    return state.workspaceInvitations
  },
}

export default {
  namespaced: true,
  state,
  getters,
  actions,
  mutations,
}
