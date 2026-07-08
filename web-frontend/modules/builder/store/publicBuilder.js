import PublishedBuilderService from '@baserow/modules/builder/services/publishedBuilder'

const state = () => ({})

const mutations = {}

const actions = {
  async fetchById({ dispatch }, { builderId }) {
    const { $client } = this
    const { data } = await PublishedBuilderService($client).fetchById(builderId)

    return await dispatch('application/forceCreate', data, { root: true })
  },

  async fetchPreview({ dispatch }) {
    const { $client } = this
    const { data } = await PublishedBuilderService($client).fetchPreview()

    return await dispatch('application/forceCreate', data, { root: true })
  },

  async fetchByDomain({ dispatch }, { domain }) {
    const { $client } = this
    const { data } =
      await PublishedBuilderService($client).fetchByDomain(domain)

    return await dispatch('application/forceCreate', data, { root: true })
  },
}

const getters = {}

export default {
  namespaced: true,
  state,
  getters,
  actions,
  mutations,
}
