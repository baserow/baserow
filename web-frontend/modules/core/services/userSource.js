export default (client) => {
  return {
    fetchAll(applicationId) {
      return client.get(`/application/${applicationId}/user-sources/`)
    },
    fetchUserRoles(applicationId) {
      return client.get(`/application/${applicationId}/user-sources/roles/`)
    },
    create(applicationId, userSourceType, values, beforeId = null) {
      const payload = {
        type: userSourceType,
        ...values,
      }

      if (beforeId !== null) {
        payload.before_id = beforeId
      }

      return client.post(`/application/${applicationId}/user-sources/`, payload)
    },
    update(userSourceId, values) {
      return client.patch(`/user-source/${userSourceId}/`, values)
    },
    delete(userSourceId) {
      return client.delete(`/user-source/${userSourceId}/`)
    },
    move(userSourceId, beforeId) {
      return client.patch(`/user-source/${userSourceId}/move/`, {
        before_id: beforeId,
      })
    },
    getUserSourceUsers(applicationId, search = '') {
      const params = {}
      if (search) {
        params.search = search
      }

      return client.get(
        `/application/${applicationId}/list-user-source-users/`,
        { params }
      )
    },
    forceAuthenticate(userSourceId, userId) {
      return client.post(`/user-source/${userSourceId}/force-token-auth`, {
        user_id: userId,
      })
    },
    authenticate(userSourceId, credentials) {
      return client.post(`/user-source/${userSourceId}/token-auth`, credentials)
    },
    refreshAuth(refreshToken) {
      return client.post(
        `/user-source-auth-refresh/`,
        {
          refresh_token: refreshToken,
        },
        { skipAuthRefresh: true }
      )
    },
    blacklistToken(refreshToken) {
      // Yes, we use the same service as the main auth.
      return client.post(
        '/user-source-token-blacklist/',
        {
          refresh_token: refreshToken,
        },
        { skipAuthRefresh: true }
      )
    },
  }
}
