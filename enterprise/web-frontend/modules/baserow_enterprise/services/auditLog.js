import baseService from '@baserow/modules/core/crudTable/baseService'
import jobService from '@baserow/modules/core/services/job'
import { fetchWorkspaceOptions } from '@baserow/modules/core/services/admin/workspaces'

export default (client) =>
  Object.assign(baseService(client, `/audit-log/`), {
    fetchActors(page, workspaceId = null) {
      const actorsUrl = `/audit-log/actors/`
      const params = { page }
      if (workspaceId) {
        params.workspace_id = workspaceId
      }
      return client.get(actorsUrl, { params })
    },
    fetchWorkspaces(page, search) {
      return fetchWorkspaceOptions(client, page, search)
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
