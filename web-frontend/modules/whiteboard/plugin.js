import whiteboardApplicationStore from '@baserow/modules/whiteboard/store/whiteboardApplication'
import { WhiteboardApplicationType } from '@baserow/modules/whiteboard/applicationTypes'

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
    }

    $registry.register('application', new WhiteboardApplicationType(context))
  },
})
