import addPublicAuthTokenHeader from '@baserow/modules/database/utils/publicView'

export default (client) => {
  return {
    export({ slug, values, publicAuthToken = null }) {
      const config = {}

      if (publicAuthToken) {
        addPublicAuthTokenHeader(config, publicAuthToken)
      }

      return client.post(
        `/database/view/${slug}/export-public-view/`,
        {
          ...values,
        },
        config
      )
    },
    get(jobId) {
      return client.get(`/database/view/get-public-view-export/${jobId}/`)
    },
  }
}
