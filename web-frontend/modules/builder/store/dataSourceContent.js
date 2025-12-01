import _ from 'lodash'
import Vue from 'vue'
import DataSourceService from '@baserow/modules/builder/services/dataSource'
import PublishedBuilderService from '@baserow/modules/builder/services/publishedBuilder'

const state = {}

const fetchTimeoutPerPage = {}

const mutations = {
  SET_CONTENT(state, { page, dataSourceId, value }) {
    if (!page.contents) {
      Vue.set(page, 'contents', {})
    }

    if (!_.isEqual(page.contents[dataSourceId], value)) {
      // Here we need to change the reference of the dataSourceContents object to
      // trigger computed values that use it in some situation (before the key exists
      // for instance)
      page.contents = {
        ...page.contents,
        [dataSourceId]: value,
      }
    }
  },
  CLEAR_CONTENTS(state, { page }) {
    Vue.set(page, 'contents', {})
  },
  // Clear only the contents for the specified data source.
  CLEAR_CONTENT(state, { page, dataSourceId }) {
    const contents = Object.assign({}, page.contents)
    delete contents[dataSourceId]
    Vue.set(page, 'contents', contents)
  },
  SET_LOADING(state, { page, value }) {
    page._.dataSourceContentLoading = value
  },
}

const actions = {
  /**
   * Fetch the content for every data sources of the given page.
   */
  async fetchPageDataSourceContent(
    { commit },
    { page, data: queryData, mode }
  ) {
    commit('SET_LOADING', { page, value: true })

    let service = DataSourceService
    if (['preview', 'public'].includes(mode)) {
      service = PublishedBuilderService
    }

    const failedDataSources = []
    try {
      const { data } = await service(this.app.$client).dispatchAll(
        page.id,
        queryData
      )

      Object.entries(data).forEach(([dataSourceIdStr, dataContent]) => {
        const dataSourceId = parseInt(dataSourceIdStr, 10)
        if (dataContent._error) {
          failedDataSources.push({
            id: dataSourceId,
            error: { error: dataContent._error, detail: dataContent.detail },
          })
          commit('SET_CONTENT', { page, dataSourceId, value: null })
        } else {
          commit('SET_CONTENT', { page, dataSourceId, value: dataContent })
        }
      })
    } catch (e) {
      commit('CLEAR_CONTENTS', { page })
      throw e
    }
    commit('SET_LOADING', { page, value: false })
    return failedDataSources
  },

  async fetchPageDataSourceContentById(
    { commit },
    { page, dataSourceId, dispatchContext, mode, replace = false }
  ) {
    commit('SET_LOADING', { page, value: true })

    let service = DataSourceService
    if (['preview', 'public'].includes(mode)) {
      service = PublishedBuilderService
    }

    try {
      const { data } = await service(this.app.$client).dispatch(
        dataSourceId,
        dispatchContext,
        { range: null }
      )

      if (replace) {
        commit('CLEAR_CONTENT', { page, dataSourceId })
      }

      commit('SET_CONTENT', {
        page,
        dataSourceId,
        value: data,
      })
    } catch (error) {
      commit('CLEAR_CONTENT', { page, dataSourceId })
      throw error
    }
  },

  debouncedFetchPageDataSourceContent(
    { dispatch },
    { page, data: queryData, mode }
  ) {
    if (fetchTimeoutPerPage[page.id]) {
      clearTimeout(fetchTimeoutPerPage[page.id])
    }
    fetchTimeoutPerPage[page.id] = setTimeout(() => {
      dispatch('fetchPageDataSourceContent', {
        page,
        data: queryData,
        mode,
      })
    }, 500)
  },

  clearDataSourceContent({ commit }, { page, dataSourceId }) {
    commit('SET_CONTENT', { page, dataSourceId, value: null })
  },

  clearDataSourceContents({ commit }, { page }) {
    commit('CLEAR_CONTENTS', { page })
  },
}

const getters = {
  getDataSourceContents: (state) => (page) => {
    return page.contents || {}
  },
  getLoading: (state) => (page) => {
    return page._.dataSourceContentLoading
  },
}

export default {
  namespaced: true,
  state,
  getters,
  actions,
  mutations,
}
