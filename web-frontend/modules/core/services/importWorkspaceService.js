export default (client) => {
  return {
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
        workspace_id: workspaceId,
        resource_id: resourceId,
      })
    },

    deleteResource(workspaceId, resourceId) {
      return client.delete(
        `/workspaces/${workspaceId}/import/${resourceId}/delete/`,
        {
          data: {
            workspace_id: workspaceId,
            resource_id: resourceId,
          },
        }
      )
    },
  }
}
