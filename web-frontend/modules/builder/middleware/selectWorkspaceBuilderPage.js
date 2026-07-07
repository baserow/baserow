import { StoreItemLookupError } from '@baserow/modules/core/errors'
import { normalizeError } from '@baserow/modules/database/utils/errors'

export default defineNuxtRouteMiddleware(async (to, from) => {
  const { $store, $i18n } = useNuxtApp()

  const builderId = parseInt(to.params.builderId)
  const pageId = parseInt(to.params.pageId)
  try {
    const loadedBuilder = await $store.dispatch(
      'application/selectById',
      builderId
    )

    await $store.dispatch('workspace/selectById', loadedBuilder.workspace.id)

    await $store.dispatch('page/selectById', {
      builder: loadedBuilder,
      pageId,
    })
  } catch (e) {
    const isStoreLookupError = e instanceof StoreItemLookupError
    if (e.response === undefined && !isStoreLookupError) {
      throw e
    }

    const errorStatus =
      isStoreLookupError || !e.response?.status ? 404 : e.response.status

    throw createError({
      statusCode: errorStatus,
      message:
        errorStatus === 404
          ? $i18n.t('pageEditor.pageNotFound')
          : normalizeError(e).message,
      data: {
        report: errorStatus !== 404,
      },
      fatal: true,
    })
  }
})
