import AgentApplicationService from '@baserow_enterprise/services/agentApplication'

export const state = () => ({
  agent: null,
  loading: false,
  triggers: [],
  triggersLoading: false,
  tools: [],
  toolsLoading: false,
  channels: [],
  channelsLoading: false,
})

export const mutations = {
  SET_AGENT(state, agent) {
    state.agent = agent
  },
  SET_LOADING(state, value) {
    state.loading = value
  },
  UPDATE_AGENT(state, values) {
    if (state.agent) {
      Object.assign(state.agent, values)
    }
  },
  SET_TRIGGERS(state, triggers) {
    state.triggers = triggers
  },
  SET_TRIGGERS_LOADING(state, value) {
    state.triggersLoading = value
  },
  ADD_TRIGGER(state, trigger) {
    state.triggers.push(trigger)
  },
  UPDATE_TRIGGER(state, { triggerId, values }) {
    const index = state.triggers.findIndex(
      (trigger) => trigger.id === triggerId
    )
    if (index !== -1) {
      state.triggers.splice(index, 1, { ...state.triggers[index], ...values })
    }
  },
  REMOVE_TRIGGER(state, triggerId) {
    const index = state.triggers.findIndex(
      (trigger) => trigger.id === triggerId
    )
    if (index !== -1) {
      state.triggers.splice(index, 1)
    }
  },
  SET_TOOLS(state, tools) {
    state.tools = tools
  },
  SET_TOOLS_LOADING(state, value) {
    state.toolsLoading = value
  },
  ADD_TOOL(state, tool) {
    state.tools.push(tool)
  },
  UPDATE_TOOL(state, { toolId, values }) {
    const index = state.tools.findIndex((tool) => tool.id === toolId)
    if (index !== -1) {
      state.tools.splice(index, 1, { ...state.tools[index], ...values })
    }
  },
  REMOVE_TOOL(state, toolId) {
    const index = state.tools.findIndex((tool) => tool.id === toolId)
    if (index !== -1) {
      state.tools.splice(index, 1)
    }
  },
  SET_CHANNELS(state, channels) {
    state.channels = channels
  },
  SET_CHANNELS_LOADING(state, value) {
    state.channelsLoading = value
  },
  ADD_CHANNEL(state, channel) {
    state.channels.push(channel)
  },
  UPDATE_CHANNEL(state, { channelId, values }) {
    const index = state.channels.findIndex(
      (channel) => channel.id === channelId
    )
    if (index !== -1) {
      state.channels.splice(index, 1, { ...state.channels[index], ...values })
    }
  },
  REMOVE_CHANNEL(state, channelId) {
    const index = state.channels.findIndex(
      (channel) => channel.id === channelId
    )
    if (index !== -1) {
      state.channels.splice(index, 1)
    }
  },
}

export const actions = {
  async fetch({ commit }, { applicationId }) {
    commit('SET_LOADING', true)
    try {
      const { data } = await AgentApplicationService(this.$client).getAgent(
        applicationId
      )
      commit('SET_AGENT', data)
      return data
    } finally {
      commit('SET_LOADING', false)
    }
  },
  forceUpdate({ commit, state }, { values }) {
    if (state.agent === null) {
      commit('SET_AGENT', values)
    } else {
      commit('UPDATE_AGENT', values)
    }
  },
  async update({ dispatch, state }, { agentId, values }) {
    const oldValues = Object.keys(values).reduce((result, key) => {
      result[key] = state.agent?.[key]
      return result
    }, {})

    dispatch('forceUpdate', { values })

    try {
      const { data } = await AgentApplicationService(this.$client).updateAgent(
        agentId,
        values
      )
      const update = Object.keys(values).reduce((result, key) => {
        result[key] = data[key]
        return result
      }, {})
      dispatch('forceUpdate', { values: update })
      return data
    } catch (error) {
      dispatch('forceUpdate', { values: oldValues })
      throw error
    }
  },
  async fetchTriggers({ commit }, { applicationId }) {
    commit('SET_TRIGGERS_LOADING', true)
    try {
      const { data } = await AgentApplicationService(this.$client).getTriggers(
        applicationId
      )
      commit('SET_TRIGGERS', data)
      return data
    } finally {
      commit('SET_TRIGGERS_LOADING', false)
    }
  },
  async createTrigger({ commit }, { applicationId, values }) {
    const { data } = await AgentApplicationService(this.$client).createTrigger(
      applicationId,
      values
    )
    commit('ADD_TRIGGER', data)
    return data
  },
  async updateTrigger({ commit }, { triggerId, values }) {
    const { data } = await AgentApplicationService(this.$client).updateTrigger(
      triggerId,
      values
    )
    commit('UPDATE_TRIGGER', { triggerId, values: data })
    return data
  },
  async deleteTrigger({ commit }, { triggerId }) {
    await AgentApplicationService(this.$client).deleteTrigger(triggerId)
    commit('REMOVE_TRIGGER', triggerId)
  },
  async fetchTools({ commit }, { applicationId }) {
    commit('SET_TOOLS_LOADING', true)
    try {
      const { data } = await AgentApplicationService(this.$client).getTools(
        applicationId
      )
      commit('SET_TOOLS', data)
      return data
    } finally {
      commit('SET_TOOLS_LOADING', false)
    }
  },
  async createTool({ commit }, { applicationId, values }) {
    const { data } = await AgentApplicationService(this.$client).createTool(
      applicationId,
      values
    )
    commit('ADD_TOOL', data)
    return data
  },
  async updateTool({ commit }, { toolId, values }) {
    const { data } = await AgentApplicationService(this.$client).updateTool(
      toolId,
      values
    )
    commit('UPDATE_TOOL', { toolId, values: data })
    return data
  },
  async deleteTool({ commit }, { toolId }) {
    await AgentApplicationService(this.$client).deleteTool(toolId)
    commit('REMOVE_TOOL', toolId)
  },
  async fetchChannels({ commit }, { applicationId }) {
    commit('SET_CHANNELS_LOADING', true)
    try {
      const { data } = await AgentApplicationService(this.$client).getChannels(
        applicationId
      )
      commit('SET_CHANNELS', data)
      return data
    } finally {
      commit('SET_CHANNELS_LOADING', false)
    }
  },
  async createChannel({ commit }, { applicationId, values }) {
    const { data } = await AgentApplicationService(this.$client).createChannel(
      applicationId,
      values
    )
    commit('ADD_CHANNEL', data)
    return data
  },
  async updateChannel({ commit, state }, { channelId, values }) {
    const channel = state.channels.find((c) => c.id === channelId)
    // Optimistically apply everything except the config, because the config
    // sent to the server can contain plain secrets while the stored config is
    // the masked public version.
    const optimistic = { ...values }
    delete optimistic.config
    const oldValues =
      channel &&
      Object.keys(optimistic).reduce((result, key) => {
        result[key] = channel[key]
        return result
      }, {})
    if (channel && Object.keys(optimistic).length > 0) {
      commit('UPDATE_CHANNEL', { channelId, values: optimistic })
    }
    try {
      const { data } = await AgentApplicationService(
        this.$client
      ).updateChannel(channelId, values)
      commit('UPDATE_CHANNEL', { channelId, values: data })
      return data
    } catch (error) {
      if (channel && Object.keys(optimistic).length > 0) {
        commit('UPDATE_CHANNEL', { channelId, values: oldValues })
      }
      throw error
    }
  },
  async deleteChannel({ commit }, { channelId }) {
    await AgentApplicationService(this.$client).deleteChannel(channelId)
    commit('REMOVE_CHANNEL', channelId)
  },
}

export const getters = {
  getAgent: (state) => state.agent,
  isLoading: (state) => state.loading,
  getTriggers: (state) => state.triggers,
  isTriggersLoading: (state) => state.triggersLoading,
  getTools: (state) => state.tools,
  isToolsLoading: (state) => state.toolsLoading,
  getChannels: (state) => state.channels,
  isChannelsLoading: (state) => state.channelsLoading,
}

export default {
  namespaced: true,
  state,
  getters,
  actions,
  mutations,
}
