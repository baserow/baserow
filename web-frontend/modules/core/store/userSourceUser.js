import jwtDecode from 'jwt-decode'

import UserSourceService from '@baserow/modules/core/services/userSource'

import {
  setToken,
  unsetToken,
  userSourceCookieTokenName,
} from '@baserow/modules/core/utils/auth'

export const state = () => ({
  // The currentApplication is used in the clientHandler because we have no way to know
  // If the a request is done for the page editor or the template.
  currentApplication: null,
})

const checkApplication = (application) => {
  if (!application.userSourceUser) {
    application.userSourceUser = {
      refreshing: false,
      token: null,
      refreshToken: null,
      tokenUpdatedAt: 0,
      tokenPayload: null,
      user: { email: '', id: 0, username: '', role: '', user_source_uid: '' },
      authenticated: false,
    }
  }
}

export const mutations = {
  SET_TOKENS(state, { application, access, refresh, tokenUpdatedAt }) {
    checkApplication(application)

    application.userSourceUser = {
      ...application.userSourceUser,
      token: access,
      refreshToken: refresh,
      tokenUpdatedAt: tokenUpdatedAt || new Date().getTime(),
      tokenPayload: jwtDecode(access),
    }
  },
  SET_USER_DATA(state, { application, data }) {
    checkApplication(application)

    application.userSourceUser = {
      ...application.userSourceUser,
      user: { ...data },
    }
  },
  CLEAR_USER_DATA(state, { application }) {
    checkApplication(application)

    application.userSourceUser = {
      ...application.userSourceUser,
      user: {},
    }
  },
  LOGOFF(state, { application }) {
    checkApplication(application)

    application.userSourceUser = {
      ...application.userSourceUser,
      refreshing: false,
      token: null,
      refreshToken: null,
      tokenUpdatedAt: 0,
      tokenPayload: null,
      user: {},
      authenticated: false,
    }
  },
  SET_AUTHENTICATED(state, { application, authenticated }) {
    checkApplication(application)

    application.userSourceUser.authenticated = authenticated
  },
  SET_REFRESHING(state, { application, refreshing }) {
    checkApplication(application)
    application.userSourceUser.refreshing = refreshing
  },
  SET_CURRENT_APPLICATION(state, { application }) {
    state.currentApplication = application
  },
}

export const actions = {
  setCurrentApplication({ commit }, { application }) {
    commit('SET_CURRENT_APPLICATION', { application })
  },
  async forceAuthenticate({ dispatch }, { application, userSource, user }) {
    const { $registry, $i18n, $client, $config } = this
    const {
      data: { access_token: access, refresh_token: refresh },
    } = await UserSourceService($client).forceAuthenticate(
      userSource.id,
      user.id
    )
    dispatch('login', {
      application,
      userSource,
      access,
      refresh,
      setCookie: false,
    })
  },
  async authenticate(
    { dispatch },
    { application, userSource, credentials, setCookie }
  ) {
    const { $registry, $i18n, $client, $config } = this
    const {
      data: { access_token: access, refresh_token: refresh },
    } = await UserSourceService($client).authenticate(
      userSource.id,
      credentials
    )
    dispatch('login', {
      application,
      userSource,
      access,
      refresh,
      setCookie,
    })
  },
  async login(
    { commit, getters },
    { application, access, refresh, tokenUpdatedAt, setCookie = true }
  ) {
    const nuxtApp = this.app
    commit('SET_TOKENS', { application, access, refresh, tokenUpdatedAt })
    const tokenPayload = jwtDecode(access)
    commit('SET_USER_DATA', {
      application,
      data: {
        id: tokenPayload.user_id,
        username: tokenPayload.username,
        email: tokenPayload.email,
        user_source_uid: tokenPayload.user_source_uid,
        role: tokenPayload.role,
      },
    })
    commit('SET_AUTHENTICATED', { application, authenticated: true })

    if (setCookie) {
      // Set the token for next page load
      await setToken(
        nuxtApp,
        getters.refreshToken(application),
        userSourceCookieTokenName,
        {
          sameSite: 'Lax',
        }
      )
    }
  },

  /**
   * Logs off the user by removing the token as a cookie and clearing the user
   * data.
   */
  async logoff({ commit, getters }, { application, invalidateToken = true }) {
    await unsetToken(this.app, userSourceCookieTokenName)
    if (!getters.isAuthenticated(application)) {
      return
    }

    const refreshToken = getters.refreshToken(application)
    commit('LOGOFF', { application })

    if (refreshToken && invalidateToken) {
      await UserSourceService(this.$client).blacklistToken(refreshToken)
    }
  },

  /**
   * Refresh the existing token. If successful commit the new token and start a
   * new refresh timeout. If unsuccessful the existing cookie and user data is
   * cleared.
   */
  async refreshAuth(
    { getters, dispatch, commit },
    { application, token = null }
  ) {
    const refreshToken = token || getters.refreshToken(application)

    if (!refreshToken) {
      throw new Error('Invalid refresh token')
    }

    commit('SET_REFRESHING', { application, refreshing: true })

    try {
      const tokenUpdatedAt = new Date().getTime()
      const {
        data: { refresh_token: refresh = null, access_token: access },
      } = await UserSourceService(this.$client).refreshAuth(refreshToken)

      // if ROTATE_REFRESH_TOKEN=False in the backend the response will not contain
      // a new refresh token. In that case, we keep the one we just used.
      dispatch('login', {
        application,
        refresh: refresh || refreshToken,
        access,
        tokenUpdatedAt,
      })
    } finally {
      commit('SET_REFRESHING', { application, refreshing: false })
    }
  },
}

export const getters = {
  getCurrentApplication: (state) => {
    return state.currentApplication
  },
  isAuthenticated: (state) => (application) => {
    return !!application?.userSourceUser?.authenticated
  },
  isRefreshing: (state) => (application) => {
    return application.userSourceUser.refreshing
  },
  accessToken: (state) => (application) => {
    return application.userSourceUser.token
  },
  refreshToken: (state) => (application) => {
    if (!Object.prototype.hasOwnProperty.call(application, 'userSourceUser')) {
      return null
    }
    return application.userSourceUser.refreshToken
  },
  role(state) {
    if (!state.authenticated) {
      return ''
    }
    return state.user.role
  },
  getUser: (state, getters) => (application) => {
    if (getters.isAuthenticated(application)) {
      return application.userSourceUser.user
    }
    return { email: '', id: 0, username: '', role: '', user_source_uid: '' }
  },
  shouldRefreshToken: (state, getters) => (application) => {
    // the user must be authenticated to refresh the token
    if (!getters.isAuthenticated(application)) {
      return false
    }

    const data = application.userSourceUser.tokenPayload
    const now = new Date().getTime()
    const tokenLifespan = (data.exp - data.iat) * 1000
    return (
      (now - application.userSourceUser.tokenUpdatedAt) / tokenLifespan > 0.8
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
