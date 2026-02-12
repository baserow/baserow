const STORAGE_KEY = 'tcr-theme'
const VALID_THEMES = ['dark', 'light', 'system']

function getSystemTheme() {
  if (typeof window === 'undefined') return 'dark'
  const preferLight = window.matchMedia('(prefers-color-scheme: light)').matches
  return preferLight ? 'light' : 'dark'
}

function applyTheme(preference) {
  if (typeof document === 'undefined') return
  const html = document.documentElement
  if (preference === 'system') {
    html.removeAttribute('data-theme')
  } else {
    html.setAttribute('data-theme', preference)
  }
}

export const state = () => ({
  preference: 'system',
  resolved: 'dark',
})

export const getters = {
  getPreference(state) {
    return state.preference
  },
  getResolved(state) {
    return state.resolved
  },
}

export const mutations = {
  SET_THEME(state, { preference, resolved }) {
    state.preference = preference
    state.resolved = resolved
  },
}

export const actions = {
  init({ dispatch }) {
    if (typeof window === 'undefined') return

    const stored = localStorage.getItem(STORAGE_KEY)
    const preference = VALID_THEMES.includes(stored) ? stored : 'system'

    dispatch('setTheme', preference)

    const mediaQuery = window.matchMedia('(prefers-color-scheme: light)')
    mediaQuery.addEventListener('change', () => {
      const currentPref = localStorage.getItem(STORAGE_KEY) || 'system'
      if (currentPref === 'system') {
        dispatch('setTheme', 'system')
      }
    })
  },

  setTheme({ commit }, preference) {
    if (!VALID_THEMES.includes(preference)) return

    const resolved = preference === 'system' ? getSystemTheme() : preference

    commit('SET_THEME', { preference, resolved })
    applyTheme(preference)

    if (typeof localStorage !== 'undefined') {
      localStorage.setItem(STORAGE_KEY, preference)
    }
  },
}

export default {
  namespaced: true,
  state,
  getters,
  mutations,
  actions,
}
