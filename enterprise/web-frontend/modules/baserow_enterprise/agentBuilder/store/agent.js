import { StoreItemLookupError } from '@baserow/modules/core/errors'
import AgentService from '@baserow_enterprise/agentBuilder/services/agent'
import { generateHash } from '@baserow/modules/core/utils/hashing'

export default {
  namespaced: true,
  state: () => ({ selectedId: null }),
  mutations: {
    SET_AGENTS(state, { agentBuilder, agents }) {
      agentBuilder.agents = agents
    },
    UPSERT_AGENT(state, { agentBuilder, agent }) {
      const existing = agentBuilder.agents.find(({ id }) => id === agent.id)
      if (existing) {
        Object.assign(existing, agent)
      } else {
        agentBuilder.agents.push(agent)
      }
    },
    DELETE_AGENT(state, { agentBuilder, agentId }) {
      const index = agentBuilder.agents.findIndex(({ id }) => id === agentId)
      if (index !== -1) {
        agentBuilder.agents.splice(index, 1)
      }
      if (state.selectedId === agentId) {
        state.selectedId = null
      }
    },
    SELECT_AGENT(state, agentId) {
      state.selectedId = agentId
    },
    ORDER_AGENTS(state, { agentBuilder, order }) {
      for (const agent of agentBuilder.agents) {
        const index = order.indexOf(generateHash(agent.id))
        if (index !== -1) {
          agent.order = index + 1
        }
      }
    },
  },
  actions: {
    async fetch({ commit }, agentBuilder) {
      const { data } = await AgentService(this.$client).fetchAll(
        agentBuilder.id
      )
      commit('SET_AGENTS', { agentBuilder, agents: data })
    },
    async create({ commit }, { agentBuilder, name }) {
      const { data: agent } = await AgentService(this.$client).create(
        agentBuilder.id,
        name
      )
      commit('UPSERT_AGENT', { agentBuilder, agent })
      return agent
    },
    async read({ commit }, { agentBuilder, agentId }) {
      const { data: agent } = await AgentService(this.$client).read(agentId)
      if (agent.agent_builder_id !== agentBuilder.id) {
        throw new StoreItemLookupError('Agent not found in this Agent Builder.')
      }
      commit('UPSERT_AGENT', { agentBuilder, agent })
      return agent
    },
    async update({ commit }, { agentBuilder, agent, values }) {
      const { data } = await AgentService(this.$client).update(agent.id, values)
      commit('UPSERT_AGENT', { agentBuilder, agent: data })
    },
    async delete({ dispatch }, { agentBuilder, agent }) {
      await AgentService(this.$client).delete(agent.id)
      await dispatch('forceDelete', { agentBuilder, agentId: agent.id })
    },
    forceUpsert({ commit }, payload) {
      commit('UPSERT_AGENT', payload)
    },
    async forceDelete({ commit, state }, { agentBuilder, agentId }) {
      const wasSelected = state.selectedId === agentId
      commit('DELETE_AGENT', { agentBuilder, agentId })
      if (wasSelected) {
        await this.app.$router.push({
          name: 'agent-builder',
          params: { agentBuilderId: agentBuilder.id },
        })
      }
    },
    select({ commit }, agentId) {
      commit('SELECT_AGENT', agentId)
    },
  },
  getters: {
    getSelectedId: (state) => state.selectedId,
    getOrdered: () => (agentBuilder) =>
      [...(agentBuilder.agents || [])].sort((a, b) => a.order - b.order),
  },
}
