export default (client) => {
  return {
    fetchAll() {
      return client.get('/templates/')
    },
    fetchOwn({ offset = 0, limit = 20, search = '' } = {}) {
      const params = { view: 'flat', type: 'user', owned: true, offset, limit }
      if (search) {
        params.search = search
      }
      return client.get('/templates/', { params })
    },
    /**
     * Lists the public user templates of everyone on this instance, the viewer's
     * own first. The page continues after the `cursor`, the `next_cursor` of the
     * previous page.
     */
    fetchListed({
      cursor = null,
      limit = 20,
      search = '',
      categoryId = null,
    } = {}) {
      const params = { view: 'flat', type: 'user', listed: true, limit }
      if (cursor !== null) {
        params.cursor = cursor
      }
      if (search) {
        params.search = search
      }
      if (categoryId !== null) {
        params.category = categoryId
      }
      return client.get('/templates/', { params })
    },
    // The categories holding at least one public user template.
    fetchListedCategories() {
      return client.get('/templates/', {
        params: { view: 'listed_categories' },
      })
    },
    fetch(slug) {
      return client.get(`/templates/${slug}/`)
    },
    install(workspaceId, templateId) {
      return client.post(`/templates/install/${workspaceId}/${templateId}/`)
    },
    /**
     * Installs the template into the workspace. The `revisionId` is the one of
     * the template that was shown, so that the install is refused if the template
     * was updated since.
     */
    asyncInstall(
      workspaceId,
      templateId,
      { latest = false, revisionId = null } = {}
    ) {
      const params = latest ? { latest: true } : {}
      if (revisionId !== null) {
        params.revision_id = revisionId
      }
      return client.post(
        `/templates/install/${workspaceId}/${templateId}/async/`,
        null,
        { params }
      )
    },
    delete(slug) {
      return client.delete(`/templates/${slug}/`)
    },
    /**
     * Makes a template of the user public or private. A template is only made
     * public if `revisionId`, the revision the user was shown, is still its
     * latest one.
     */
    setListed(slug, listed, revisionId = null) {
      return client.patch(`/templates/${slug}/`, {
        listed,
        ...(listed && { public_listing_consent: true }),
        ...(listed && revisionId !== null && { revision_id: revisionId }),
      })
    },
  }
}
