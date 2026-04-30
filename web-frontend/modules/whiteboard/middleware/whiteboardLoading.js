import { StoreItemLookupError } from '@baserow/modules/core/errors'

/**
 * Middleware that toggles the whiteboard loading state and selects the
 * application before navigating into a /whiteboard/:whiteboardId route.
 */
export default defineNuxtRouteMiddleware(async (to, from) => {
  const nuxtApp = useNuxtApp()
  const store = nuxtApp.$store

  const parseIntOrNull = (x) => (x != null ? parseInt(x) : null)

  const toWhiteboardId = parseIntOrNull(to?.params?.whiteboardId)
  const fromWhiteboardId = parseIntOrNull(from?.params?.whiteboardId)
  const differentWhiteboardId = fromWhiteboardId !== toWhiteboardId

  if (toWhiteboardId) {
    try {
      const whiteboard = await store.dispatch(
        'application/selectById',
        toWhiteboardId
      )
      await store.dispatch('workspace/selectById', whiteboard.workspace.id)
    } catch (e) {
      if (e.response === undefined && !(e instanceof StoreItemLookupError)) {
        throw e
      }
      throw createError({
        statusCode: 404,
        message: 'Whiteboard not found.',
      })
    }
  }

  if (import.meta.server || !from || differentWhiteboardId) {
    await store.dispatch('whiteboardApplication/setLoading', true)
  }
})
