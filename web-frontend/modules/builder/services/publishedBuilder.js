export default (client) => {
  return {
    publish(domain) {
      return client.post(`builder/domains/${domain.id}/publish/async/`, {
        domain_id: domain.id,
      })
    },
    fetchByDomain(domain) {
      return client.get(`builder/domains/published/by_name/${domain}/`)
    },
    fetchById(builderId) {
      return client.get(`builder/domains/published/by_id/${builderId}/`)
    },
    fetchElements(page) {
      return client.get(`builder/domains/published/page/${page.id}/elements/`)
    },
    fetchDataSources(pageId) {
      return client.get(
        `builder/domains/published/page/${pageId}/data_sources/`
      )
    },
    fetchWorkflowActions(pageId) {
      return client.get(
        `builder/domains/published/page/${pageId}/workflow_actions/`
      )
    },
    dispatch(
      dataSourceId,
      dispatchContext,
      { range, filters = {}, sortings = null, search = '', searchMode = '' }
    ) {
      // Using POST Http method here is not Restful but it the cleanest way to send
      // data with the call without relying on GET parameter and serialization of
      // complex object.
      const params = new URLSearchParams()
      if (range) {
        params.append('offset', range[0])
        params.append('count', range[1])
      }

      Object.keys(filters).forEach((key) => {
        filters[key].forEach((value) => {
          params.append(key, value)
        })
      })

      if (sortings || sortings === '') {
        params.append('order_by', sortings)
      }

      if (search) {
        params.append('search_query', search)
        if (searchMode) {
          params.append('search_mode', searchMode)
        }
      }

      return client.post(
        `builder/domains/published/data-source/${dataSourceId}/dispatch/`,
        dispatchContext,
        { params }
      )
    },
    dispatchAll(pageId, params) {
      return client.post(
        `builder/domains/published/page/${pageId}/dispatch-data-sources/`,
        params
      )
    },
  }
}
