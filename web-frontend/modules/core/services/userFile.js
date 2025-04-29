export default (client) => {
  return {
    uploadFile(file, onUploadProgress = function () {}, cancelToken = null) {
      const formData = new FormData()
      formData.append('file', file)

      const config = {
        cancelToken,
        onUploadProgress,
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      }

      return client.post('/user-files/upload-file/', formData, config)
    },
    uploadViaURL(url) {
      return client.post('/user-files/upload-via-url/', { url })
    },
    async getFileMetadata(url) {
      try {
        const response = await fetch(url, {
          method: 'HEAD',
        })
        const contentType = response.headers.get('content-type')
        const size = response.headers.get('content-length')
        return { contentType, size }
      } catch (e) {
        return { contentType: 'application/octet-stream', size: 0 }
      }
    },
  }
}
