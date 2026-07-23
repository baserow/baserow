import pageStore from '@baserow/modules/builder/store/page'
import elementStore from '@baserow/modules/builder/store/element'
import domainStore from '@baserow/modules/builder/store/domain'
import publicBuilderStore from '@baserow/modules/builder/store/publicBuilder'
import dataSourceStore from '@baserow/modules/builder/store/dataSource'
import pageParameterStore from '@baserow/modules/builder/store/pageParameter'
import dataSourceContentStore from '@baserow/modules/builder/store/dataSourceContent'
import elementContentStore from '@baserow/modules/builder/store/elementContent'
import themeStore from '@baserow/modules/builder/store/theme'
import builderWorkflowActionStore from '@baserow/modules/builder/store/builderWorkflowAction'
import formDataStore from '@baserow/modules/builder/store/formData'
import builderToast from '@baserow/modules/builder/store/builderToast'
import { registerRealtimeEvents } from '@baserow/modules/builder/realtime'
import {
  DuplicatePageJobType,
  PublishBuilderJobType,
} from '@baserow/modules/builder/jobTypes'
import { BuilderApplicationType } from '@baserow/modules/builder/applicationTypes'
import { BuilderSearchType } from '@baserow/modules/builder/searchTypes'
import { searchTypeRegistry } from '@baserow/modules/core/search/types/registry'

export default defineNuxtPlugin({
  name: 'builder',
  dependsOn: ['core', 'store'],
  async setup(nuxtApp) {
    const { $store, $registry } = nuxtApp
    const context = { app: nuxtApp }

    $store.registerModuleNuxtSafe('page', pageStore)
    $store.registerModuleNuxtSafe('element', elementStore)
    $store.registerModuleNuxtSafe('domain', domainStore)
    $store.registerModuleNuxtSafe('publicBuilder', publicBuilderStore)
    $store.registerModuleNuxtSafe('dataSource', dataSourceStore)
    $store.registerModuleNuxtSafe('pageParameter', pageParameterStore)
    $store.registerModuleNuxtSafe('dataSourceContent', dataSourceContentStore)
    $store.registerModuleNuxtSafe('elementContent', elementContentStore)
    $store.registerModuleNuxtSafe('theme', themeStore)
    $store.registerModuleNuxtSafe(
      'builderWorkflowAction',
      builderWorkflowActionStore
    )
    $store.registerModuleNuxtSafe('formData', formDataStore)
    $store.registerModuleNuxtSafe('builderToast', builderToast)

    $registry.registerNamespace('builderSettings')
    $registry.registerNamespace('element')
    $registry.registerNamespace('device')
    $registry.registerNamespace('pageHeaderItem')
    $registry.registerNamespace('domain')
    $registry.registerNamespace('pageSettings')
    $registry.registerNamespace('pathParamType')
    $registry.registerNamespace('builderDataProvider')
    $registry.registerNamespace('themeConfigBlock')
    $registry.registerNamespace('fontFamily')
    $registry.registerNamespace('builderPageDecorator')
    $registry.registerNamespace('pageSidePanel')
    $registry.registerNamespace('queryParamType')
    $registry.registerNamespace('pageAction')
    $registry.registerNamespace('collectionField')

    $registry.register('application', new BuilderApplicationType(context))

    // Job types stay eager: the sidebar jobs panel resolves them on any page.
    $registry.register('job', new DuplicatePageJobType(context))
    $registry.register('job', new PublishBuilderJobType(context))

    searchTypeRegistry.register(new BuilderSearchType(context))

    // Elements, theme blocks, workflow actions, fonts etc. load on builder routes.
    $registry.registerDomainLoader('builder', async () => {
      const { default: register } =
        await import('@baserow/modules/builder/lazyRegistrations')
      register(nuxtApp)
    })
  },
})
