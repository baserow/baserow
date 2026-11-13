import baseService from '@baserow/modules/core/crudTable/baseService'

export default (client) =>
  Object.assign(
    baseService(
      client,
      ({ workspaceId }) => `/identities/workspace/${workspaceId}/`
    ),
    {
      create(workspaceId, values) {
        return client.post(`/identities/workspace/${workspaceId}/`, values)
      },
      /** Fetch every page, optionally limiting the results to selectable identities. */
      async list(workspaceId, { forSelection = false } = {}) {
        const url = `/identities/workspace/${workspaceId}/`
        const params = { size: 200 }
        if (forSelection) {
          params.for_selection = true
        }
        const response = await client.get(url, {
          params: { ...params, page: 1 },
        })
        const results = [...response.data.results]
        let next = response.data.next
        let page = 2
        while (next) {
          const { data } = await client.get(url, {
            params: { ...params, page },
          })
          results.push(...data.results)
          next = data.next
          page++
        }
        return {
          ...response,
          data: { ...response.data, results, next: null },
        }
      },
      /** Fetch one page of the Identities of the workspace. */
      listPage(
        workspaceId,
        { page = 1, search = '', size = 100, forSelection = false } = {}
      ) {
        const params = { page, size }
        if (forSelection) {
          params.for_selection = true
        }
        if (search) {
          params.search = search
        }
        return client.get(`/identities/workspace/${workspaceId}/`, { params })
      },
      update(identityId, values) {
        return client.patch(`/identities/${identityId}/`, values)
      },
      delete(identityId) {
        return client.delete(`/identities/${identityId}/`)
      },
    }
  )
