import AgentService from '@baserow/modules/core/services/agent'

const upsertAgent = (state, agent) => {
  const index = state.items.findIndex((item) => item.id === agent.id)
  if (index === -1) {
    state.items.push(agent)
  } else {
    state.items.splice(index, 1, agent)
  }
}

export const state = () => ({
  items: [],
  revisions: {},
})

export const mutations = {
  MERGE_ITEMS(state, agents) {
    agents.forEach((agent) => upsertAgent(state, agent))
  },
  UPSERT_ITEM(state, agent) {
    upsertAgent(state, agent)
    state.revisions[agent.workspace_id] =
      (state.revisions[agent.workspace_id] || 0) + 1
  },
  DELETE_ITEM(state, { workspaceId, agentId }) {
    const index = state.items.findIndex((item) => item.id === agentId)
    if (index !== -1) {
      state.items.splice(index, 1)
    }
    state.revisions[workspaceId] = (state.revisions[workspaceId] || 0) + 1
  },
}

export const actions = {
  async fetchPage({ commit }, { args }) {
    const response = await AgentService(this.$client).fetch(...args)
    commit('MERGE_ITEMS', response.data.results)
    return response
  },
  async fetchAll({ commit }, workspaceId) {
    const { data } = await AgentService(this.$client).list(workspaceId)
    commit('MERGE_ITEMS', data.results)
    return data.results
  },
  async create({ dispatch }, { workspaceId, values }) {
    const { data } = await AgentService(this.$client).create(
      workspaceId,
      values
    )
    return dispatch('forceCreate', data)
  },
  forceCreate({ commit }, agent) {
    commit('UPSERT_ITEM', agent)
    return agent
  },
  async update({ dispatch }, { agentId, values }) {
    const { data } = await AgentService(this.$client).update(agentId, values)
    return dispatch('forceUpdate', data)
  },
  forceUpdate({ commit }, agent) {
    commit('UPSERT_ITEM', agent)
    return agent
  },
  async delete({ dispatch }, agent) {
    await AgentService(this.$client).delete(agent.id)
    dispatch('forceDelete', {
      workspaceId: agent.workspace_id,
      agentId: agent.id,
    })
  },
  forceDelete({ commit }, payload) {
    commit('DELETE_ITEM', payload)
  },
}

export const getters = {
  get: (state) => (agentId) => state.items.find((item) => item.id === agentId),
  getAllInWorkspace: (state) => (workspaceId) =>
    state.items.filter((item) => item.workspace_id === workspaceId),
  getRevision: (state) => (workspaceId) => state.revisions[workspaceId] || 0,
}

export default { namespaced: true, state, mutations, actions, getters }
