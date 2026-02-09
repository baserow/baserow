import authProviderService from '@baserow/modules/core/services/authProvider'

function populateProviderLoginOptions(authProviderType, registry) {
  const type = registry.get('authProvider', authProviderType.type)
  return type.populateLoginOptions(authProviderType)
}

export const state = () => ({
  loginOptionsLoaded: false,
  loginOptions: {},
})

export const mutations = {
  SET_LOGIN_OPTIONS(state, loginOptions) {
    state.loginOptions = loginOptions
    state.loginOptionsLoaded = true
  },
}

export const actions = {
  async fetchLoginOptions({ commit }) {
    const { $client, $registry } = this

    const { data } = await authProviderService($client).fetchLoginOptions()

    const loginOptions = {}

    const dataValues = Object.values(data)

    for (const providerTypeLoginOption of dataValues) {
      try {
        const loginOption = populateProviderLoginOptions(
          providerTypeLoginOption,
          $registry
        )
        loginOptions[providerTypeLoginOption.type] = loginOption
      } catch (error) {
        console.error('Error in populateProviderLoginOptions:', error)
        throw error
      }
    }
    commit('SET_LOGIN_OPTIONS', loginOptions)
    return loginOptions
  },
}

export const getters = {
  areLoginOptionsLoaded(state) {
    return state.loginOptionsLoaded
  },
  getLoginOptionsForType: (state) => (type) => {
    return state.loginOptions[type]
  },
  getAllLoginButtons: (state) => {
    let optionsWithButton = []
    for (const loginOption of Object.values(state.loginOptions)) {
      if (
        loginOption.hasLoginButton &&
        loginOption.items &&
        loginOption.items.length > 0
      ) {
        optionsWithButton = optionsWithButton.concat(loginOption.items)
      }
    }
    return optionsWithButton
  },
  getAllLoginActions: (state) => {
    const loginActions = []
    for (const loginOption of Object.values(state.loginOptions)) {
      if (loginOption.hasLoginAction) {
        loginActions.push(loginOption)
      }
    }
    return loginActions
  },
  getPasswordLoginEnabled: (state) => {
    return !!state.loginOptions.password
  },
  getDefaultRedirectUrl: (state) => {
    const loginOptionsArr = Object.values(state.loginOptions)
    const possibleRedirectLoginOptions = loginOptionsArr.filter(
      (loginOption) => loginOption.default_redirect_url
    )
    if (
      loginOptionsArr.length === 1 &&
      possibleRedirectLoginOptions.length === 1
    ) {
      return possibleRedirectLoginOptions[0].default_redirect_url
    }
    return null
  },
}

export default {
  namespaced: true,
  state,
  getters,
  actions,
  mutations,
}
