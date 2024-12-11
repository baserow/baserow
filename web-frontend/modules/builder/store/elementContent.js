import DataSourceService from '@baserow/modules/builder/services/dataSource'
import PublishedBuilderService from '@baserow/modules/builder/services/publishedBuilder'
import { rangeDiff } from '@baserow/modules/core/utils/range'

const state = {}

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
    element._.hasNextPage = false
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
     * The nested collection fetches its content by finding, either the root-level
     * collection element with a dataSource, or its immediate parent with a schema property.
     *
     * If we have a parent with a schema property: this nested collection element
     * is a child of a collection element using a schema property as well, e.g.:
     *
     * - Root collection element (with a dataSource):
     *       - Parent collection element (with a schema property)
     *           - Grandchild collection element (this `element`!) with a schema property.
     *
     * If we don't have a parent element with a schema property, we are a child of
     * the root collection element with a dataSource, e.g.:
     *
     * - Root collection element (with a dataSource):
     *      - Parent collection element (this `element`!) with a schema property.
     */
    if (dataSource === null) {
      if (!element.schema_property) {
        // We have a collection element that supports schema properties, and
        // we have A) no data source and B) no schema property
        // or,
        // We have a collection element that doesn't support schema properties
        // (record selector), and there's no data source.
        commit('SET_LOADING', { element, value: false })
        return
      }

      commit('SET_LOADING', { element, value: true })

      // Collect all collection element ancestors, with a `data_source_id`.
      const collectionAncestors = this.app.store.getters[
        'element/getAncestors'
      ](page, element, {
        predicate: (ancestor) =>
          this.app.$registry.get('element', ancestor.type)
            .isCollectionElement && ancestor.data_source_id !== null,
      })

      // Pluck out the root ancestor, which has a data source.
      const rootAncestorWithDataSource = collectionAncestors[0]

      // Next, find this element's parent.
      const parent = this.app.store.getters['element/getParent'](page, element)

      // If the parent has a `schema_property`, we'll want to use the
      // parent's element content for `element` to use. If the parent
      // doesn't have a property, we'll access to the root ancestor's
      // (which has a data source) for the content.
      const targetElement = parent.schema_property
        ? parent
        : rootAncestorWithDataSource

      const targetContent =
        this.app.store.getters['elementContent/getElementContent'](
          targetElement
        )

      let elementContent = []
      if (parent.schema_property) {
        // If the parent has a `schema_property`, it's an array of values
        // *inside* `schema_property`, so we just copy the array.
        elementContent = [...targetContent]
      } else {
        // Build a new array of content, for this `element`, which
        // will only contain the property `schema_property`.
        elementContent = targetContent.map((obj) => ({
          [element.schema_property]: obj[element.schema_property],
        }))
      }

      commit('CLEAR_CONTENT', {
        element,
      })
      commit('SET_CONTENT', {
        element,
        value: elementContent,
      })
      commit('SET_LOADING', { element, value: false })
      return
    }

    const serviceType = this.app.$registry.get('service', dataSource.type)

    // We have a data source, but if it doesn't return a list,
    // it needs to have a `schema_property` to work correctly.
    if (!serviceType.returnsList && element.schema_property === null) {
      // If we previously had a list data source, we might have content,
      // so rather than leave the content *until a schema property is set*,
      // clear it.
      commit('CLEAR_CONTENT', {
        element,
      })
      commit('SET_LOADING', { element, value: false })
      return
    }

    try {
      if (serviceType.isValid(dataSource)) {
        let rangeToFetch = range
        if (!replace) {
          // Let's compute the range that really needs to be fetched if necessary
          const [offset, count] = range
          rangeToFetch = rangeDiff(getters.getContentRange(element), [
            offset,
            offset + count,
          ])

          // Everything is already loaded we can quit now
          if (!rangeToFetch) {
            return
          }
          rangeToFetch = [rangeToFetch[0], rangeToFetch[1] - rangeToFetch[0]]
        }

        let service = DataSourceService
        if (['preview', 'public'].includes(mode)) {
          service = PublishedBuilderService
        }

        commit('SET_LOADING', { element, value: true })
        const { data } = await service(this.app.$client).dispatch(
          dataSource.id,
          dispatchContext,
          { range: rangeToFetch, filters, sortings, search, searchMode }
        )

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
            value: data.results,
            range,
          })
        } else {
          // The service type returns a single row of results, we'll set the
          // content using the element's schema property. Not how there's no
          // range for paging, all results are set at once. We default to an
          // empty array if the property doesn't exist, this will happen if
          // the property has been removed since the initial configuration.
          const propertyValue = data[element.schema_property] || []
          commit('SET_CONTENT', {
            element,
            value: propertyValue,
          })
        }

        commit('SET_HAS_MORE_PAGE', {
          element,
          value: hasNextPage,
        })
      } else {
        commit('CLEAR_CONTENT', {
          element,
        })
      }
    } catch (e) {
      // If fetching the content failed, and we're trying to
      // replace the element's content, then we'll clear the
      // element instead of reverting to our previousContent
      // as it could be out of date anyway.
      if (replace) {
        commit('CLEAR_CONTENT', { element })
      }
      throw e
    } finally {
      commit('SET_LOADING', { element, value: false })
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
  getElementContent:
    (state) =>
    (element, applicationContext = {}) => {
      // If we have a recordIndexPath to work with, and the element has
      // its content loaded, then we're fetching content for a nested
      // collection+container element, which has a schema property. We'll
      // return the content at a specific index path, and from that property.
      const { recordIndexPath = [] } = applicationContext
      if (recordIndexPath.length && element._.content.length) {
        const contentAtIndex = element._.content[recordIndexPath[0]]
        return contentAtIndex?.[element.schema_property] || []
      }
      return element._.content
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
