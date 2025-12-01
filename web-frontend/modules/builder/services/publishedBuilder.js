import { prepareDispatchParams } from '@baserow/modules/builder/utils/params'

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
      dispatchRefinements,
      signal = null
    ) {
      const params = prepareDispatchParams(dispatchRefinements)
      const config = { params }

      if (signal !== null) {
        config.signal = signal
      }

      return client.post(
        `builder/domains/published/data-source/${dataSourceId}/dispatch/`,
        { metadata: dispatchContext },
        config
      )
    },
    dispatchAll(pageId, params) {
      return client.post(
        `builder/domains/published/page/${pageId}/dispatch-data-sources/`,
        { metadata: params }
      )
    },
  }
}
