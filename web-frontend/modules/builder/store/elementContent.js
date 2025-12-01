import DataSourceService from '@baserow/modules/builder/services/dataSource'
import PublishedBuilderService from '@baserow/modules/builder/services/publishedBuilder'
import { rangeDiff } from '@baserow/modules/core/utils/range'
import axios from 'axios'

const state = {}

const queriesInProgress = {}

const mutations = {
  SET_CONTENT(state, { element, value, range = null }) {
    // Return early when value is null since there is nothing to set.
    if (value === null) {
      return
    }

    // If we have no range, then the `value` is the full content for `element`,
    // we'll apply it and return early. This will happen if we are setting the
    // content of a collection element's `schema_property`.
    if (range === null) {
      element._.content = value
      return
    }
    const [offset] = range
    const missingIndexes = offset + value.length - element._.content.length

    let newContent

    if (missingIndexes > 0) {
      newContent = element._.content.concat(Array(missingIndexes).fill(null))
    } else {
      newContent = [...element._.content]
    }

    value.forEach((record, index) => {
      newContent[offset + index] = record
    })

    element._.content = newContent
  },
  SET_HAS_MORE_PAGE(state, { element, value }) {
    element._.hasNextPage = value
  },

  CLEAR_CONTENT(state, { element }) {
    element._.content = []
    element._.hasNextPage = true
  },
  TRIGGER_RESET(state, { element }) {
    element._.reset += 1
  },
  SET_LOADING(state, { element, value }) {
    element._.contentLoading = value
  },
}

const actions = {
  /**
   * Fetch the data from the server and add them to the element store.
   * @param {object} page - the page object
   * @param {object} element - the element object
   * @param {object} dataSource - the data source we want to dispatch
   * @param {object} range - the range of the data we want to fetch
   * @param {object} filters - the adhoc filters to apply to the data
   * @param {object} sortings - the adhoc sortings to apply to the data
   * @param {object} search - the adhoc search to apply to the data
   * @param {string} searchMode - the search mode to apply to the data.
   * @param {string} mode - the mode of the application
   * @param {object} dispatchContext - the context to dispatch to the data
   * @param {bool} replace - if we want to replace the current content
   * @param {object} data - the query body
   */
  async fetchElementContent(
    { commit, getters },
    {
      page,
      element,
      dataSource,
      range,
      filters = {},
      sortings = null,
      search = '',
      searchMode = '',
      mode,
      data: dispatchContext,
      replace = false,
    }
  ) {
    /**
     * If `dataSource` is `null`, this means that we are trying to fetch the content
     * of a nested collection element, such as a repeat nested in a repeat.
     *
     * No content is stored for this element directly. It's content will be deduced
     * from the applicationContext and the content of the parent element
     */
    if (!dataSource) {
      // No data source means no content for this element directly. It will then take
      // it's content from the parent element so we can fake the end of the loading.
      commit('SET_HAS_MORE_PAGE', { element, value: false })
      commit('SET_LOADING', { element, value: false })
      return
    }

    const serviceType = this.app.$registry.get('service', dataSource.type)

    try {
      let rangeToFetch = range
      if (!replace) {
        // Let's compute the range that really needs to be fetched if necessary
        const [offset, count] = range
        rangeToFetch = rangeDiff(getters.getContentRange(element), [
          offset,
          offset + count,
        ])

        // Everything is already loaded we can quit now
        if (!rangeToFetch || !getters.getHasMorePage(element)) {
          commit('SET_LOADING', { element, value: false })
          return
        }
        rangeToFetch = [rangeToFetch[0], rangeToFetch[1] - rangeToFetch[0]]
      }

      let service = DataSourceService
      if (['preview', 'public'].includes(mode)) {
        service = PublishedBuilderService
      }

      if (!queriesInProgress[element.id]) {
        queriesInProgress[element.id] = {}
      }

      if (queriesInProgress[element.id][`${rangeToFetch}`]) {
        queriesInProgress[element.id][`${rangeToFetch}`].abort()
      }

      commit('SET_LOADING', { element, value: true })

      queriesInProgress[element.id][`${rangeToFetch}`] = global.AbortController
        ? new AbortController()
        : null

      const { data } = await service(this.app.$client).dispatch(
        dataSource.id,
        dispatchContext,
        { range: rangeToFetch, filters, sortings, search, searchMode },
        queriesInProgress[element.id][`${rangeToFetch}`]?.signal
      )

      delete queriesInProgress[element.id][`${rangeToFetch}`]

      // With a list-type data source, the data object will return
      // a `has_next_page` field for paging to the next set of results.
      const { has_next_page: hasNextPage = false } = data

      if (replace) {
        commit('CLEAR_CONTENT', {
          element,
        })
      }

      if (serviceType.returnsList) {
        // The service type returns a list of results, we'll set the content
        // using the results key and set the range for future paging.
        commit('SET_CONTENT', {
          element,
          value: data.results.map((row) => ({
            ...row,
            __recordId__: row[serviceType.getIdProperty(service, row)],
          })),
          range,
        })
      } else {
        // The service type returns a single row of results, we'll set the
        // content using the element's schema property. Not how there's no
        // range for paging, all results are set at once. We default to an
        // empty array if the property doesn't exist, this will happen if
        // the property has been removed since the initial configuration.
        commit('SET_CONTENT', {
          element,
          value: data,
        })
      }

      commit('SET_HAS_MORE_PAGE', {
        element,
        value: hasNextPage,
      })
    } catch (e) {
      if (!axios.isCancel(e)) {
        // If fetching the content failed, and we're trying to
        // replace the element's content, then we'll clear the
        // element instead of reverting to our previousContent
        // as it could be out of date anyway.
        if (replace) {
          commit('CLEAR_CONTENT', { element })
        }
        // Let's stop all other queries
        Object.values(queriesInProgress[element.id] || {}).forEach(
          (controller) => controller.abort()
        )
        queriesInProgress[element.id] = {}
        throw e
      }
    } finally {
      // If this element has no active queries in progress, then
      // we can set loading to false. The variable will be a blank
      // object if there was an early return and no HTTP request
      // was made.
      if (
        queriesInProgress[element.id] &&
        !Object.keys(queriesInProgress[element.id]).length
      ) {
        commit('SET_LOADING', { element, value: false })
      }
    }
  },
  clearElementContent({ commit }, { element }) {
    commit('CLEAR_CONTENT', { element })
  },

  triggerElementContentReset({ commit }, { element }) {
    commit('TRIGGER_RESET', { element })
  },
}

const getters = {
  getElementContent: (state) => (element) => {
    return element._.content || []
  },
  getHasMorePage: (state) => (element) => {
    return element._.hasNextPage
  },
  getLoading: (state) => (element) => {
    return element._.contentLoading
  },
  getReset: (state) => (element) => {
    return element._.reset
  },
  getContentRange: (state) => (element) => {
    return [0, element._.content.length]
  },
}

export default {
  namespaced: true,
  state,
  getters,
  actions,
  mutations,
}
