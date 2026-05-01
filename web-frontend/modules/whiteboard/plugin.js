import whiteboardApplicationStore from '@baserow/modules/whiteboard/store/whiteboardApplication'
import whiteboardCommentsStore from '@baserow/modules/whiteboard/store/whiteboardComments'
import { WhiteboardApplicationType } from '@baserow/modules/whiteboard/applicationTypes'
import {
  WhiteboardCommentMentionNotificationType,
  WhiteboardCommentReplyNotificationType,
} from '@baserow/modules/whiteboard/notificationTypes'

export default defineNuxtPlugin({
  name: 'whiteboard',
  dependsOn: ['core', 'store'],
  async setup(nuxtApp) {
    const { $store, $registry } = nuxtApp
    const context = { app: nuxtApp }

    if (!$store.hasModule('whiteboardApplication')) {
      $store.registerModuleNuxtSafe(
        'whiteboardApplication',
        whiteboardApplicationStore
      )
      $store.registerModuleNuxtSafe(
        'template/whiteboardApplication',
        whiteboardApplicationStore
      )
    }
    if (!$store.hasModule('whiteboardComments')) {
      $store.registerModuleNuxtSafe(
        'whiteboardComments',
        whiteboardCommentsStore
      )
    }

    $registry.register('application', new WhiteboardApplicationType(context))

    $registry.register(
      'notification',
      new WhiteboardCommentMentionNotificationType(context)
    )
    $registry.register(
      'notification',
      new WhiteboardCommentReplyNotificationType(context)
    )
  },
})
