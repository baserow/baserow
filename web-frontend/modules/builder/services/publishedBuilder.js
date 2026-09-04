import { prepareDispatchParams } from '@baserow/modules/builder/utils/params'
import { getBuilderPreviewApiPath } from '@baserow/modules/builder/utils/preview'

const getRenderPath = (builderId, previewPath, publicPath) =>
  builderId
    ? getBuilderPreviewApiPath(builderId, previewPath)
    : `builder/domains/published/${publicPath}`

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
    fetchPreview(builderId) {
      return client.get(getBuilderPreviewApiPath(builderId, 'current/'))
    },
    createPreviewGrant(builderId, path) {
      return client.post(`builder/preview/${builderId}/grant/`, { path })
    },
    fetchElements(page, builderId = null) {
      return client.get(
        getRenderPath(
          builderId,
          `pages/${page.id}/elements/`,
          `page/${page.id}/elements/`
        )
      )
    },
    fetchDataSources(pageId, builderId = null) {
      return client.get(
        getRenderPath(
          builderId,
          `pages/${pageId}/data-sources/`,
          `page/${pageId}/data_sources/`
        )
      )
    },
    fetchWorkflowActions(pageId, builderId = null) {
      return client.get(
        getRenderPath(
          builderId,
          `pages/${pageId}/workflow-actions/`,
          `page/${pageId}/workflow_actions/`
        )
      )
    },
    dispatch(
      dataSourceId,
      dispatchContext,
      dispatchRefinements,
      signal = null,
      builderId = null
    ) {
      const params = prepareDispatchParams(dispatchRefinements)
      const config = { params }

      if (signal !== null) {
        config.signal = signal
      }

      return client.post(
        getRenderPath(
          builderId,
          `data-sources/${dataSourceId}/dispatch/`,
          `data-source/${dataSourceId}/dispatch/`
        ),
        { metadata: dispatchContext },
        config
      )
    },
    dispatchAll(pageId, params, builderId = null) {
      return client.post(
        getRenderPath(
          builderId,
          `pages/${pageId}/dispatch-data-sources/`,
          `page/${pageId}/dispatch-data-sources/`
        ),
        { metadata: params }
      )
    },
  }
}
