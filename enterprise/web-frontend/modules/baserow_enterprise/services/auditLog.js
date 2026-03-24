import baseService from '@baserow/modules/core/crudTable/baseService'
import jobService from '@baserow/modules/core/services/job'
import { ADMIN_WORKSPACE_OPTIONS_URL } from '@baserow_enterprise/services/adminWorkspaces'

export default (client) => {
  return Object.assign(baseService(client, `/audit-log/`), {
    fetchUsers(page, search, workspaceId = null) {
      const usersUrl = `/audit-log/users/`
      const userPaginatedService = baseService(client, usersUrl)
      const filters = {}
      if (workspaceId) {
        filters.workspace_id = workspaceId
      }
      return userPaginatedService.fetch(usersUrl, page, search, [], filters)
    },
    fetchWorkspaces(page, search) {
      const workspacePaginatedService = baseService(
        client,
        ADMIN_WORKSPACE_OPTIONS_URL
      )
      return workspacePaginatedService.fetch(
        ADMIN_WORKSPACE_OPTIONS_URL,
        page,
        search,
        [],
        {}
      )
    },
    fetchActionTypes(page, search, workspaceId = null) {
      const actionTypesUrl = `/audit-log/action-types/`
      const actionTypePaginatedService = baseService(client, actionTypesUrl)
      const filters = {}
      if (workspaceId) {
        filters.workspace_id = workspaceId
      }
      return actionTypePaginatedService.fetch(
        actionTypesUrl,
        page,
        search,
        [],
        filters
      )
    },
    startExportCsvJob(data) {
      return client.post(`/audit-log/export/`, data)
    },
    getExportJobInfo(jobId) {
      return jobService(client).get(jobId)
    },
    async getLastExportJobs(maxCount = 3) {
      const { data } = await jobService(client).fetchAll({
        states: ['!failed'],
      })
      const jobs = data.jobs || []
      return jobs
        .filter((job) => job.type === 'audit_log_export')
        .slice(0, maxCount)
    },
  })
}
