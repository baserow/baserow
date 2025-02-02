export default (client) => {
  return {
    export(slug, values) {
      return client.post(`/database/view/${slug}/export-public-view/`, {
        ...values,
      })
    },
    get(jobId) {
      return client.get(`/database/view/get-public-view-export/${jobId}/`)
    },
  }
}
