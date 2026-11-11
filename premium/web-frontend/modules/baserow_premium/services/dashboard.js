export default (client) => {
  return {
    /**
     * Updates the dashboard attributes that are only available with a premium
     * license, such as hiding the Baserow logo on the shared dashboard.
     */
    update(dashboardId, values) {
      return client.patch(`/dashboard/${dashboardId}/premium/`, values)
    },
  }
}
