export const handleDispatchError = (err, instance, context = '') => {
  const $t = (...params) => {
    return instance.i18n ? instance.i18n.t(...params) : instance.$t(...params)
  }

  const $store = instance.store || instance.$store

  let toastTitle = $t('builderToast.defaultTitle')
  let toastMessage = $t('builderToast.defaultMessage')

  const errorType = err.response?.data?.error

  switch (errorType) {
    case 'ERROR_SERVICE_INVALID_DISPATCH_CONTEXT':
      toastTitle = $t('builderToast.invalidContextTitle')
      toastMessage = $t('builderToast.invalidContextMessage')
      break
    case 'ERROR_SERVICE_INVALID_DISPATCH_CONTEXT_CONTENT':
      toastTitle = $t('builderToast.InvalidContentTitle')
      toastMessage = $t('builderToast.invalidContentMessage')
      break
    case 'ERROR_SERVICE_IMPROPERLY_CONFIGURED':
      toastTitle = $t('builderToast.serviceMisconfiguredTitle')
      toastMessage = $t('builderToast.serviceMisconfiguredMessage')
      break
  }
  return $store.dispatch('builderToast/error', {
    title: toastTitle,
    message: `${context}${toastMessage}`,
    details: err.response?.data?.detail,
  })
}
