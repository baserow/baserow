import { ApplicationType } from '@baserow/modules/core/applicationTypes'
import BuilderForm from '@baserow/modules/builder/components/form/BuilderForm'
import SidebarComponentBuilder from '@baserow/modules/builder/components/sidebar/SidebarComponentBuilder'
import { populatePage } from '@baserow/modules/builder/store/page'
import PageTemplate from '@baserow/modules/builder/components/page/PageTemplate'
import PageTemplateSidebar from '@baserow/modules/builder/components/page/PageTemplateSidebar'
import BuilderApplicationContext from '@baserow/modules/builder/components/application/BuilderApplicationContext'
import { DataProviderType } from '@baserow/modules/core/dataProviderTypes'
import { DEVELOPMENT_STAGES } from '@baserow/modules/core/constants'

export class BuilderApplicationType extends ApplicationType {
  static getType() {
    return 'builder'
  }

  getIconClass() {
    return 'baserow-icon-application'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('applicationType.builder')
  }

  getNamePlural() {
    const { i18n } = this.app
    return i18n.t('applicationType.builders')
  }

  getDescription() {
    const { i18n } = this.app
    return i18n.t('applicationType.builderDesc')
  }

  getDefaultName() {
    const { i18n } = this.app
    return i18n.t('applicationType.builderDefaultName')
  }

  supportsTrash() {
    return false
  }

  getApplicationFormComponent() {
    return BuilderForm
  }

  getSidebarComponent() {
    return SidebarComponentBuilder
  }

  getApplicationContextComponent() {
    return BuilderApplicationContext
  }

  getTemplateSidebarComponent() {
    return PageTemplateSidebar
  }

  getTemplatesPageComponent() {
    return PageTemplate
  }

  getTemplatePage(application) {
    const notSharedPages = application.pages.filter((p) => p.shared === false)
    if (notSharedPages.length === 0) {
      return null
    }
    return {
      builder: application,
      page: notSharedPages[0],
    }
  }

  populate(application) {
    const values = super.populate(application)
    values.pages = values.pages.map(populatePage)
    if (!values.integrations) {
      values.integrations = []
    }
    if (!values.user_sources) {
      values.user_sources = []
    }
    if (!values.selectedElement) {
      values.selectedElement = null
    }
    values._loadedOnce = false

    values.userSourceUser = null
    return values
  }

  getFrontendUrls(application) {
    const domains = this.app.store.getters['domain/getDomains']

    return [
      ...domains.map((domain) => {
        const url = new URL(this.app.$config.PUBLIC_WEB_FRONTEND_URL)
        return `${url.protocol}//${domain.domain_name}${
          url.port ? `:${url.port}` : ''
        }`
      }),
    ]
  }

  delete(application) {
    const { store, router } = this.app
    const pageSelected = store.getters['page/getVisiblePages'](
      application
    ).some((page) => page._.selected)

    if (pageSelected) {
      router.push({ name: 'dashboard' })
    }
  }

  async loadExtraData(builder, mode) {
    const { store, $registry } = this.app
    if (!builder._loadedOnce) {
      const sharedPage = store.getters['page/getSharedPage'](builder)
      await Promise.all([
        store.dispatch('userSource/fetch', {
          application: builder,
        }),
        store.dispatch('integration/fetch', {
          application: builder,
        }),
        // Fetch shared data sources
        store.dispatch('dataSource/fetch', {
          page: sharedPage,
        }),
        store.dispatch('element/fetch', {
          builder,
          page: sharedPage,
        }),
        store.dispatch('builderWorkflowAction/fetch', { page: sharedPage }),
      ])

      // Initialize application shared stuff like data sources
      await DataProviderType.initOnceAll(
        $registry.getAll('builderDataProvider'),
        {
          builder,
          mode,
        }
      )

      await store.dispatch('application/forceUpdate', {
        application: builder,
        data: { _loadedOnce: true },
      })
    }
  }

  async select(application) {
    const { router, store, i18n } = this.app

    const pages = store.getters['page/getVisiblePages'](application)

    if (pages.length > 0) {
      await router.push({
        name: 'builder-page',
        params: {
          builderId: application.id,
          pageId: pages[0].id,
        },
      })
      return true
    } else {
      store.dispatch('toast/error', {
        title: i18n.t('applicationType.cantSelectPageTitle'),
        message: i18n.t('applicationType.cantSelectPageDescription'),
      })
      return false
    }
  }

  prepareForStoreUpdate(application, data) {
    if (Object.prototype.hasOwnProperty.call(data, 'pages')) {
      delete data.pages
    }

    if (Object.prototype.hasOwnProperty.call(data, 'theme')) {
      delete data.theme
    }

    return data
  }

  get developmentStage() {
    return DEVELOPMENT_STAGES.BETA
  }

  isVisible(application) {
    // We don't want to show a builder application the user doesn't
    // have the permission to list pages.
    return this.app.$hasPermission(
      'builder.list_pages',
      application,
      application.workspace.id
    )
  }

  getOrder() {
    return 70
  }
}
