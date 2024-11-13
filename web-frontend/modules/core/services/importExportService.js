export default (client) => {
  return {
    exportApplications(workspaceId, values) {
      return client.post(`/workspaces/${workspaceId}/export/async/`, values)
    },
    listExports(workspaceId) {
      return client.get(`/workspaces/${workspaceId}/export/`)
    },
    uploadFile(
      workspaceId,
      file,
      onUploadProgress = function () {},
      cancelToken = null
    ) {
      const formData = new FormData()
      formData.append('file', file)

      const config = {
        cancelToken,
        onUploadProgress,
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      }

      return client.post(
        `/workspaces/${workspaceId}/import/upload-file/`,
        formData,
        config
      )
    },
    triggerImport(workspaceId, resourceId) {
      return client.post(`/workspaces/${workspaceId}/import/async/`, {
        resource_id: resourceId,
      })
    },

    deleteResource(workspaceId, resourceId) {
      return client.delete(`/workspaces/${workspaceId}/import/${resourceId}/`, {
        data: {
          resource_id: resourceId,
        },
      })
    },
  }
}
