export const state = () => ({
  routeComponentMounted: false,
  currentRoute: null,
})

export const mutations = {
  SET_ROUTE_MOUNTED(state, { mounted, route }) {
    state.routeComponentMounted = mounted
    state.currentRoute = route
  },
}

export const getters = {
  routeMounted(state) {
    return state.routeComponentMounted ? state.currentRoute : null
  },
}

export default {
  namespaced: true,
  state,
  getters,
  mutations,
}
