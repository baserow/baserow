import FieldRulesService from '@baserow/modules/database/services/fieldRules'
import _ from 'lodash'

export const state = () => ({ tables: {} })

export const actions = {
  async fetchInitial({ commit, dispatch, getters }, { tableId }) {
    if (getters.getLoading({ tableId }) === true) {
      return
    }

    commit('SET_LOADING', { tableId, value: true })
    try {
      const { data } = await FieldRulesService(this.$client).getRules(tableId)

      commit('CLEAR_RULES', { tableId })
      data.forEach((rule) => {
        commit('ADD_RULE', { tableId, rule })
      })

      return getters.getRules({ tableId })
    } finally {
      commit('SET_LOADING', { tableId, value: false })
    }
  },
  async addRule({ commit, dispatch, getters }, { tableId, rule }) {
    commit('SET_LOADING', { tableId, value: true })
    try {
      const { data } = await FieldRulesService(this.$client).createRule(
        tableId,
        rule
      )
      commit('ADD_RULE', { tableId, rule: data })
      this.$bus.$emit('fieldRules/updated', data)
      return getters.getRuleById({ tableId, ruleId: data.id })
    } finally {
      commit('SET_LOADING', { tableId, value: false })
    }
  },
  /** this changes the rule locally. It is used in propagating changes from
   *  broadcast events */
  ruleChanged({ commit, dispatch, getters }, { tableId, ruleId, rule }) {
    commit('UPDATE_RULE', { tableId, ruleId, rule })
    this.$bus.$emit('fieldRules/updated', rule)
  },

  async updateRule({ commit, dispatch, getters }, { tableId, ruleId, rule }) {
    commit('SET_LOADING', { tableId, value: true })
    try {
      const { data } = await FieldRulesService(this.$client).updateRule(
        tableId,
        ruleId,
        rule
      )

      await dispatch('ruleChanged', { tableId, ruleId, rule: data })
      return getters.getRuleById({ tableId, ruleId: data.id })
    } finally {
      commit('SET_LOADING', { tableId, value: false })
    }
  },
  async deleteRule({ commit, dispatch }, { tableId, ruleId }) {
    commit('SET_LOADING', { tableId, value: true })
    try {
      await FieldRulesService(this.$client).deleteRule(tableId, ruleId)

      commit('REMOVE_RULE', { tableId, ruleId })
    } finally {
      commit('SET_LOADING', { tableId, value: false })
    }
  },
}

export const mutations = {
  CLEAR_RULES(state, { tableId }) {
    state.tables[tableId] = { rules: [] }
  },

  ADD_RULE(state, { tableId, rule }) {
    if (tableId !== rule.table_id) {
      throw new Error(`${tableId} mismatch for the rule ${rule.table_id}`)
    }
    const ruleId = rule.id
    const table = state.tables[tableId] || {}
    const rules = table.rules || []
    if (rules.find((r) => r.id === ruleId)) {
      throw new Error(`Rule with id ${ruleId} already exists.`)
    }

    rules.push(rule)
    table.rules = rules
    state.tables[tableId] = table
  },
  REMOVE_RULE(state, { tableId, ruleId }) {
    const table = state.tables[tableId] || {}
    const rules = table.rules || []
    const index = rules.findIndex((r) => r.id === ruleId)
    if (index === -1) {
      throw new Error(`Rule with id ${ruleId} does not exist.`)
    }
    rules.splice(index, 1)
  },
  SET_LOADING(state, { tableId, value }) {
    const table = state.tables[tableId] || { loading: value }
    state.tables[tableId] = table
  },
  UPDATE_RULE(state, { tableId, ruleId, rule }) {
    const existing = state.tables[tableId]?.rules.find((r) => r.id === ruleId)
    if (!existing) {
      throw new Error(`Rule with id ${ruleId} does not exist.`)
    }
    Object.assign(existing, rule)
  },
}

export const getters = {
  hasRules(state) {
    return ({ tableId }) => {
      return _.isArray(state.tables[tableId]?.rules || null)
    }
  },
  getLoading(state) {
    return ({ tableId }) => {
      return state.tables[tableId]?.loading || false
    }
  },
  getRules(state) {
    return ({ tableId }) => {
      return state.tables[tableId]?.rules || []
    }
  },
  getRuleById(state) {
    return ({ tableId, ruleId }) => {
      const table = state.tables[tableId]
      if (!table) {
        return null
      }
      const rule = (table.rules || []).find((r) => r.id === ruleId)
      if (!rule) {
        return null
      }
      return rule
    }
  },
  getRulesByType(state) {
    return ({ tableId, ruleType }) => {
      const rules = state.tables[tableId]?.rules || []
      return rules.filter((r) => r.type === ruleType)
    }
  },
  getInvalidRules(state) {
    return ({ tableId }) => {
      const rules = state.tables[tableId]?.rules || []
      return rules.filter((r) => r.is_valid === false)
    }
  },
}

export default {
  namespaced: true,
  state,
  getters,
  actions,
  mutations,
}
