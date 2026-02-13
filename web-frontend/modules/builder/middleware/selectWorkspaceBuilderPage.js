import { StoreItemLookupError } from '@baserow/modules/core/errors'

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
    if (e.response === undefined && !(e instanceof StoreItemLookupError)) {
      throw e
    }

    throw createError({
      statusCode: 404,
      message: $i18n.t('pageEditor.pageNotFound'),
      fatal: false,
    })
  }
})
