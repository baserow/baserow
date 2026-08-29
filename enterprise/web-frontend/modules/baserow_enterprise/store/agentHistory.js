import AgentApplicationService from '@baserow_enterprise/services/agentApplication'

const RUNNING_STATUSES = ['in_progress', 'canceling']
const PAGE_SIZE = 50

function sortChats(chats) {
  chats.sort(
    (a, b) =>
      new Date(b.updated_on).getTime() - new Date(a.updated_on).getTime()
  )
}

export const state = () => ({
  chats: [],
  usage: null,
  loading: false,
  // Pagination of the fetched pages; realtime upserts can grow `chats`
  // independently, so the fetched offset is tracked separately.
  fetchedCount: 0,
  hasMore: false,
})

export const mutations = {
  SET_CHATS(state, chats) {
    sortChats(chats)
    state.chats = chats
  },
  APPEND_CHATS(state, chats) {
    for (const chat of chats) {
      const index = state.chats.findIndex((c) => c.id === chat.id)
      if (index !== -1) {
        state.chats.splice(index, 1, { ...state.chats[index], ...chat })
      } else {
        state.chats.push(chat)
      }
    }
    sortChats(state.chats)
  },
  UPSERT_CHAT(state, chat) {
    const index = state.chats.findIndex((c) => c.id === chat.id)
    if (index !== -1) {
      state.chats.splice(index, 1, { ...state.chats[index], ...chat })
    } else {
      state.chats.push(chat)
    }
    sortChats(state.chats)
  },
  REMOVE_CHAT(state, chatId) {
    const index = state.chats.findIndex((chat) => chat.id === chatId)
    if (index !== -1) {
      state.chats.splice(index, 1)
    }
  },
  SET_USAGE(state, usage) {
    state.usage = usage
  },
  SET_LOADING(state, value) {
    state.loading = value
  },
  SET_PAGINATION(state, { fetchedCount, hasMore }) {
    state.fetchedCount = fetchedCount
    state.hasMore = hasMore
  },
}

export const actions = {
  clear({ commit }) {
    commit('SET_CHATS', [])
    commit('SET_USAGE', null)
    commit('SET_PAGINATION', { fetchedCount: 0, hasMore: false })
  },
  async fetch({ commit }, { applicationId }) {
    commit('SET_LOADING', true)
    try {
      const { data } = await AgentApplicationService(this.$client).getChats(
        applicationId,
        { limit: PAGE_SIZE, offset: 0 }
      )
      commit('SET_CHATS', data.results)
      commit('SET_PAGINATION', {
        fetchedCount: data.results.length,
        hasMore: data.next !== null,
      })
      return data.results
    } finally {
      commit('SET_LOADING', false)
    }
  },
  async fetchMore({ commit, state }, { applicationId }) {
    if (!state.hasMore || state.loading) {
      return
    }
    commit('SET_LOADING', true)
    try {
      const { data } = await AgentApplicationService(this.$client).getChats(
        applicationId,
        { limit: PAGE_SIZE, offset: state.fetchedCount }
      )
      commit('APPEND_CHATS', data.results)
      commit('SET_PAGINATION', {
        fetchedCount: state.fetchedCount + data.results.length,
        hasMore: data.next !== null,
      })
      return data.results
    } finally {
      commit('SET_LOADING', false)
    }
  },
  async fetchUsage({ commit }, { applicationId }) {
    const { data } = await AgentApplicationService(this.$client).getUsage(
      applicationId
    )
    commit('SET_USAGE', data)
    return data
  },
  forceUpdateChat({ commit }, { chat }) {
    commit('UPSERT_CHAT', chat)
  },
  forceDeleteChat({ commit }, { chatId }) {
    commit('REMOVE_CHAT', chatId)
  },
}

export const getters = {
  getChats: (state) => state.chats,
  getRunningChats: (state) =>
    state.chats.filter((chat) => RUNNING_STATUSES.includes(chat.status)),
  getUsage: (state) => state.usage,
  isLoading: (state) => state.loading,
  hasMore: (state) => state.hasMore,
}

export default {
  namespaced: true,
  state,
  getters,
  actions,
  mutations,
}
