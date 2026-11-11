export default (client) => {
  return {
    /**
     * Updates the public sharing state of a dashboard: `public` and
     * `public_password`. Hiding the logo is a premium attribute with its own
     * endpoint.
     */
    updateSharing(dashboardId, values) {
      return client.patch(`/dashboard/${dashboardId}/sharing/`, values)
    },
    rotateSlug(dashboardId) {
      return client.post(`/dashboard/${dashboardId}/rotate-slug/`)
    },
  }
}
