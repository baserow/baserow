import addPublicAuthTokenHeader from '@baserow/modules/database/utils/publicView'

export default (client) => {
  const prepareRequestConfig = ({ publicAuthToken = null }) => {
    const config = { headers: {} }
    if (publicAuthToken) {
      addPublicAuthTokenHeader(config, publicAuthToken)
    }
    return config
  }

  return {
    getMetaInformation(slug, publicAuthToken = null) {
      const config = prepareRequestConfig({ publicAuthToken })
      return client.get(`/database/views/form/${slug}/submit/`, config)
    },
    submit(slug, values, publicAuthToken = null) {
      const config = prepareRequestConfig({ publicAuthToken })
      return client.post(`/database/views/form/${slug}/submit/`, values, config)
    },
    getEditRow(slug, editToken, publicAuthToken = null) {
      const config = prepareRequestConfig({ publicAuthToken })
      return client.get(
        `/database/views/form/${slug}/edit-row/${editToken}/`,
        config
      )
    },
    submitEditRow(slug, editToken, values, publicAuthToken = null) {
      const config = prepareRequestConfig({ publicAuthToken })
      return client.patch(
        `/database/views/form/${slug}/edit-row/${editToken}/`,
        values,
        config
      )
    },
    uploadFile(
      file,
      onUploadProgress = function () {},
      slug,
      publicAuthToken = null
    ) {
      const formData = new FormData()
      formData.append('file', file)

      const config = {
        onUploadProgress,
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      }

      if (publicAuthToken) {
        addPublicAuthTokenHeader(config, publicAuthToken)
      }

      return client.post(
        `/database/views/form/${slug}/upload-file/`,
        formData,
        config
      )
    },
  }
}
