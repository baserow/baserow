import undoRedoStoreModule from '../store/undoRedo'
import workspaceStoreModule from '../store/workspace'
import workspaceSearchStoreModule from '../store/workspaceSearch'
import settingsStoreModule from '../store/settings'
import notificationStoreModule from '../store/notification'
import jobStoreModule from '../store/job'
import authProviderStoreModule from '../store/authProvider'
import authStoreModule from '../store/auth'
import applicationStoreModule from '../store/application'
import userSourceUserStoreModule from '../store/userSourceUser'
import userSourceStoreModule from '../store/userSource'
import toastStoreModule from '../store/toast'
import routeMountedStoreModule from '../store/routeMounted'
import integrationStoreModule from '../store/integration'

export default defineNuxtPlugin({
  name: 'store',
  dependsOn: ['create-store', 'client-handler', 'core', 'i18n'],
  async setup(nuxtApp) {
    const { $store, $i18n, $config, $client, $registry } = nuxtApp

    $store.$i18n = $i18n
    $store.$config = $config
    $store.$client = $client
    $store.$registry = $registry
    /*if (!$store.hasModule('application')) {
      $store.registerModule('undoRedo', undoRedoStoreModule)
      $store.registerModule('workspace', workspaceStoreModule)
      $store.registerModule('settings', settingsStoreModule)
      $store.registerModule('notification', notificationStoreModule)
      $store.registerModule('job', jobStoreModule)
      $store.registerModule('authProvider', authProviderStoreModule)
      $store.registerModule('auth', authStoreModule)
      $store.registerModule('application', applicationStoreModule)
      $store.registerModule('userSourceUser', userSourceUserStoreModule)
      $store.registerModule('userSource', userSourceStoreModule)
      $store.registerModule('workspaceSearch', workspaceSearchStoreModule)
      $store.registerModule('routeMounted', routeMountedStoreModule)
      $store.registerModule('toast', toastStoreModule)
      $store.registerModule('integration', integrationStoreModule)
    }*/
  },
})
