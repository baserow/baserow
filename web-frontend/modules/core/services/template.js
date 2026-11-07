import { PRIVATE_LINK_HEADER } from '@baserow/modules/core/utils/templatePrivateLink'

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
     * own first.
     */
    fetchListed({
      offset = 0,
      limit = 20,
      search = '',
      categoryId = null,
    } = {}) {
      const params = { view: 'flat', type: 'user', listed: true, offset, limit }
      if (search) {
        params.search = search
      }
      if (categoryId !== null) {
        params.category = categoryId
      }
      return client.get('/templates/', { params })
    },
    // The categories holding at least one public user template.
    fetchPublicCategories() {
      return client.get('/templates/', {
        params: { view: 'public_categories' },
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
    /**
     * Responds with the archive of a user template (200), or with the job that
     * builds it (202), after which the archive is asked for again.
     */
    /**
     * @param {string} [privateLinkToken] The token of the private link the
     *   template was opened through, sent even once its page is left.
     */
    download(slug, revisionId, privateLinkToken = null) {
      return client.post(
        `/templates/${slug}/download/`,
        { revision_id: revisionId },
        privateLinkToken
          ? { headers: { [PRIVATE_LINK_HEADER]: privateLinkToken } }
          : {}
      )
    },
    delete(slug) {
      return client.delete(`/templates/${slug}/`)
    },
    /**
     * Makes a template of the user public or private. A template is only made
     * public with the `publicListingConsent` of its author.
     *
     * @param {string} visibility `public` or `private`.
     */
    setVisibility(slug, visibility, { publicListingConsent = false } = {}) {
      const isPublic = visibility === 'public'
      return client.patch(`/templates/${slug}/`, {
        visibility,
        ...(isPublic && { public_listing_consent: publicListingConsent }),
      })
    },
    /**
     * Creates the private link of a template of the user, or turns it off.
     */
    setPrivateLink(slug, enabled) {
      return client.patch(`/templates/${slug}/`, { private_link: enabled })
    },
    /**
     * Replaces the private link of a template of the user with a new one.
     */
    rotatePrivateLinkToken(slug) {
      return client.post(`/templates/${slug}/rotate-private-link-token/`)
    },
  }
}
