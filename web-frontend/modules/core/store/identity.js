import IdentityService from '@baserow/modules/core/services/identity'

const upsertIdentity = (state, identity) => {
  const index = state.items.findIndex((item) => item.id === identity.id)
  if (index === -1) {
    state.items.push(identity)
  } else {
    state.items.splice(index, 1, identity)
  }
}

export const state = () => ({
  items: [],
  revisions: {},
})

export const mutations = {
  MERGE_ITEMS(state, identities) {
    identities.forEach((identity) => upsertIdentity(state, identity))
  },
  UPSERT_ITEM(state, identity) {
    upsertIdentity(state, identity)
    state.revisions[identity.workspace_id] =
      (state.revisions[identity.workspace_id] || 0) + 1
  },
  DELETE_ITEM(state, { workspaceId, identityId }) {
    const index = state.items.findIndex((item) => item.id === identityId)
    if (index !== -1) {
      state.items.splice(index, 1)
    }
    state.revisions[workspaceId] = (state.revisions[workspaceId] || 0) + 1
  },
}

export const actions = {
  async fetchPage({ commit, state }, { args, workspaceId }) {
    const revision = state.revisions[workspaceId] || 0
    const response = await IdentityService(this.$client).fetch(...args)
    if ((state.revisions[workspaceId] || 0) === revision) {
      commit('MERGE_ITEMS', response.data.results)
    }
    return response
  },
  async fetchAll({ commit }, workspaceId) {
    const { data } = await IdentityService(this.$client).list(workspaceId)
    commit('MERGE_ITEMS', data.results)
    return data.results
  },
  async create({ dispatch }, { workspaceId, values }) {
    const { data } = await IdentityService(this.$client).create(
      workspaceId,
      values
    )
    return dispatch('forceCreate', data)
  },
  forceCreate({ commit, state, dispatch }, identity) {
    const exists = state.items.some((item) => item.id === identity.id)
    commit('UPSERT_ITEM', identity)
    if (!exists) {
      dispatch(
        'workspace/updateIdentitiesCount',
        { workspaceId: identity.workspace_id, delta: 1 },
        { root: true }
      )
    }
    return identity
  },
  async update({ dispatch }, { identityId, values }) {
    const { data } = await IdentityService(this.$client).update(
      identityId,
      values
    )
    return dispatch('forceUpdate', data)
  },
  forceUpdate({ commit }, identity) {
    commit('UPSERT_ITEM', identity)
    return identity
  },
  async delete({ dispatch }, identity) {
    await IdentityService(this.$client).delete(identity.id)
    dispatch('forceDelete', {
      workspaceId: identity.workspace_id,
      identityId: identity.id,
    })
  },
  forceDelete({ commit, dispatch }, payload) {
    commit('DELETE_ITEM', payload)
    dispatch(
      'workspace/updateIdentitiesCount',
      { workspaceId: payload.workspaceId, delta: -1 },
      { root: true }
    )
  },
}

export const getters = {
  get: (state) => (identityId) =>
    state.items.find((item) => item.id === identityId),
  getAllInWorkspace: (state) => (workspaceId) =>
    state.items.filter((item) => item.workspace_id === workspaceId),
  getRevision: (state) => (workspaceId) => state.revisions[workspaceId] || 0,
}

export default { namespaced: true, state, mutations, actions, getters }
