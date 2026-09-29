import { createStore } from 'vuex'

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
import presenceStoreModule from '../store/presence'
import aiProviderStoreModule from '../store/aiProvider'
import guidedTourStoreModule from '../store/guidedTour'
import agentStoreModule from '../store/agent'

export default defineNuxtPlugin({
  name: 'create-store',
  async setup(nuxtApp) {
    const store = createStore({
      modules: {
        undoRedo: undoRedoStoreModule,
        workspace: workspaceStoreModule,
        settings: settingsStoreModule,
        notification: notificationStoreModule,
        job: jobStoreModule,
        authProvider: authProviderStoreModule,
        auth: authStoreModule,
        application: applicationStoreModule,
        userSourceUser: userSourceUserStoreModule,
        userSource: userSourceStoreModule,
        workspaceSearch: workspaceSearchStoreModule,
        routeMounted: routeMountedStoreModule,
        toast: toastStoreModule,
        integration: integrationStoreModule,
        presence: presenceStoreModule,
        aiProvider: aiProviderStoreModule,
        guidedTour: guidedTourStoreModule,
        agent: agentStoreModule,
      },
    })
    nuxtApp.vueApp.use(store)
    nuxtApp.provide('store', store)
  },
})
