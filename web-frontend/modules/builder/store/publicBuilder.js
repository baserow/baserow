import PublishedBuilderService from '@baserow/modules/builder/services/publishedBuilder'

const state = {}

const mutations = {}

const actions = {
  async fetchById({ dispatch }, { builderId }) {
    const { $registry, $i18n, $client, $config } = useNuxtApp()
    const { data } = await PublishedBuilderService($client).fetchById(builderId)

    return await dispatch('application/forceCreate', data, { root: true })
  },

  async fetchByDomain({ dispatch }, { domain }) {
    const { $registry, $i18n, $client, $config } = useNuxtApp()
    const { data } = await PublishedBuilderService($client).fetchByDomain(
      domain
    )

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
