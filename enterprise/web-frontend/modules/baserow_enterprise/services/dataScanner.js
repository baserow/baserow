import baseService from '@baserow/modules/core/crudTable/baseService'
import jobService from '@baserow/modules/core/services/job'

export const DataScannerScansService = (client) => {
  const url = '/admin/data-scanner/scans/'
  return Object.assign(baseService(client, url), {
    create(data) {
      return client.post(url, data)
    },
    get(scanId) {
      return client.get(`${url}${scanId}/`)
    },
    update(scanId, data) {
      return client.patch(`${url}${scanId}/`, data)
    },
    delete(scanId) {
      return client.delete(`${url}${scanId}/`)
    },
    trigger(scanId) {
      return client.post(`${url}${scanId}/trigger/`)
    },
    fetchWorkspaceStructure(workspaceId) {
      return client.get(
        `/admin/data-scanner/workspace-structure/${workspaceId}/`
      )
    },
  })
}

export const DataScannerResultsService = (client) => {
  return Object.assign(baseService(client, '/admin/data-scanner/results/'), {
    startExportCsvJob(data) {
      return client.post('/admin/data-scanner/results/export/', data)
    },
    async getLastExportJobs(maxCount = 4) {
      const { data } = await jobService(client).fetchAll({
        states: ['!failed'],
      })
      const jobs = data.jobs || []
      return jobs
        .filter((job) => job.type === 'data_scan_result_export')
        .slice(0, maxCount)
    },
    deleteResult(resultId) {
      return client.delete(`/admin/data-scanner/results/${resultId}/`)
    },
  })
}
