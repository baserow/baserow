export default (client) => {
  return {
    dashboard(timezone = null) {
      const config = {
        params: {},
      }

      if (timezone !== null) {
        config.params.timezone = timezone
      }

      return client.get(`/admin/dashboard/`, config)
    },
  }
}
