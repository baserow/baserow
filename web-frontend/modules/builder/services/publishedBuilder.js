import { prepareDispatchParams } from '@baserow/modules/builder/utils/params'

const previewAuthConfig = { usePreviewAuth: true }

export default (client) => {
  return {
    publish(domain) {
      return client.post(`builder/domains/${domain.id}/publish/async/`, {
        domain_id: domain.id,
      })
    },
    fetchByDomain(domain) {
      return client.get(
        `builder/domains/published/by_name/${domain}/`,
        previewAuthConfig
      )
    },
    fetchById(builderId) {
      return client.get(
        `builder/domains/published/by_id/${builderId}/`,
        previewAuthConfig
      )
    },
    fetchPreview() {
      return client.get('builder/preview/current/', previewAuthConfig)
    },
    createPreviewGrant(builderId, path) {
      return client.post(`builder/preview/${builderId}/grant/`, { path })
    },
    fetchElements(page) {
      return client.get(
        `builder/domains/published/page/${page.id}/elements/`,
        previewAuthConfig
      )
    },
    fetchDataSources(pageId) {
      return client.get(
        `builder/domains/published/page/${pageId}/data_sources/`,
        previewAuthConfig
      )
    },
    fetchWorkflowActions(pageId) {
      return client.get(
        `builder/domains/published/page/${pageId}/workflow_actions/`,
        previewAuthConfig
      )
    },
    dispatch(
      dataSourceId,
      dispatchContext,
      dispatchRefinements,
      signal = null
    ) {
      const params = prepareDispatchParams(dispatchRefinements)
      const config = { params, ...previewAuthConfig }

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
        { metadata: params },
        previewAuthConfig
      )
    },
  }
}
