import isEqual from 'lodash/isEqual'
import { notifyIf } from '@baserow/modules/core/utils/error'
import AgentPermissionsService from '@baserow_enterprise/services/agentPermissions'
import { AGENT_CAPABILITIES } from '@baserow_enterprise/utils/agentPermissions'

const itemOf = (state, agentId) => {
  if (!state.items[agentId]) {
    state.items[agentId] = { rules: null, loadError: false, revision: 0 }
  }
  return state.items[agentId]
}

export const state = () => ({ items: {} })

export const mutations = {
  START_LOAD(state, agentId) {
    const item = itemOf(state, agentId)
    item.revision++
    item.loadError = false
  },
  SET_RULES(state, { agentId, rules }) {
    const item = itemOf(state, agentId)
    if (!item.rules) item.rules = {}
    // Keeping unchanged subjects preserves an open picker across permission refreshes.
    for (const capability of AGENT_CAPABILITIES) {
      if (!isEqual(item.rules[capability], rules[capability])) {
        item.rules[capability] = rules[capability]
      }
    }
  },
  SET_RULE(state, { agentId, capability, rule }) {
    const item = itemOf(state, agentId)
    // An earlier permissions refresh may still contain the previous rule.
    item.revision++
    if (item.rules) item.rules[capability] = rule
  },
  SET_LOAD_ERROR(state, agentId) {
    itemOf(state, agentId).loadError = true
  },
}

export const actions = {
  /** Loads an Agent's rules, ignoring a reply that a newer load or save replaced. */
  async fetch({ commit, state }, { agentId }) {
    commit('START_LOAD', agentId)
    const revision = state.items[agentId].revision
    const isCurrent = () => state.items[agentId].revision === revision
    try {
      const { data } = await AgentPermissionsService(this.$client).get(agentId)
      if (isCurrent()) commit('SET_RULES', { agentId, rules: data })
    } catch (error) {
      if (!isCurrent()) return
      commit('SET_LOAD_ERROR', agentId)
      notifyIf(error)
    }
  },
  /** Saves one rule; the caller handles a failure. */
  async save({ commit }, { agentId, capability, role, subjects }) {
    const { data } = await AgentPermissionsService(this.$client).update(
      agentId,
      capability,
      { role, subjects }
    )
    commit('SET_RULE', { agentId, capability, rule: data })
    return data
  },
}

export const getters = {
  get: (state) => (agentId) => state.items[agentId] || null,
}

export default {
  namespaced: true,
  state,
  getters,
  actions,
  mutations,
}
