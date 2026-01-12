<script setup>
/**
 * This page functions as a never changing path in the web-frontend that will redirect
 * the visitor to the correct page related to the provided notification type and ID.
 * The reason we have this is so that the backend doesn't need to know about the paths
 * available in the web-frontend, and won't break behavior if they change.
 */
import notificationService from '@baserow/modules/core/services/notification'

const route = useRoute()
const nuxtApp = useNuxtApp()
const workspaceId = route.params.workspaceId
const notificationId = route.params.notificationId

const { data: notification, error: loadError } = await useAsyncData(
  () => `notification:${workspaceId}:${notificationId}`,
  async () => {
    const { data } = await notificationService(nuxtApp.$client).markAsRead(
      workspaceId,
      notificationId
    )
    return data
  }
)

if (loadError.value || !notification.value) {
  throw createError({
    statusCode: 404,
    statusMessage: 'Notification not found.',
  })
}

const notificationType = nuxtApp.$registry.get(
  'notification',
  notification.value.type
)
const redirectParams = notificationType.getRoute(notification.value.data)

if (!redirectParams) {
  throw createError({
    statusCode: 404,
    statusMessage: 'Notification has no route.',
  })
}

await navigateTo(redirectParams, { replace: true })
</script>
