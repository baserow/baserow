import baseService from '@baserow/modules/core/crudTable/baseService'

export default (client) =>
  Object.assign(
    baseService(
      client,
      ({ workspaceId }) => `/agents/workspace/${workspaceId}/`
    ),
    {
      create(workspaceId, values) {
        return client.post(`/agents/workspace/${workspaceId}/`, values)
      },
      /** Fetch every page before exposing Agents to membership selectors. */
      async list(workspaceId) {
        const url = `/agents/workspace/${workspaceId}/`
        const response = await client.get(url, {
          params: { size: 200, page: 1 },
        })
        const results = [...response.data.results]
        let next = response.data.next
        let page = 2
        while (next) {
          const { data } = await client.get(url, {
            params: { size: 200, page },
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
      /** Fetch one page of the Agents of the workspace. */
      listPage(workspaceId, { page = 1, search = '', size = 100 } = {}) {
        const params = { page, size }
        if (search) {
          params.search = search
        }
        return client.get(`/agents/workspace/${workspaceId}/`, { params })
      },
      update(agentId, values) {
        return client.patch(`/agents/${agentId}/`, values)
      },
      delete(agentId) {
        return client.delete(`/agents/${agentId}/`)
      },
    }
  )
