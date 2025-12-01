<template>
  <div class="page-editor">
    <PageHeader />
    <div class="layout__col-2-2 page-editor__content">
      <div :style="{ width: `calc(100% - ${panelWidth}px)` }">
        <PagePreview />
      </div>
      <div
        class="page-editor__side-panel"
        :style="{ width: `${panelWidth}px` }"
      >
        <PageSidePanels />
      </div>
    </div>
  </div>
</template>

<script>
import { StoreItemLookupError } from '@baserow/modules/core/errors'
import PageHeader from '@baserow/modules/builder/components/page/header/PageHeader'
import PagePreview from '@baserow/modules/builder/components/page/PagePreview'
import PageSidePanels from '@baserow/modules/builder/components/page/PageSidePanels'
import { DataProviderType } from '@baserow/modules/core/dataProviderTypes'
import { BuilderApplicationType } from '@baserow/modules/builder/applicationTypes'
import ApplicationBuilderFormulaInput from '@baserow/modules/builder/components/ApplicationBuilderFormulaInput'
import _ from 'lodash'

const mode = 'editing'

export default {
  name: 'PageEditor',
  components: { PagePreview, PageHeader, PageSidePanels },
  provide() {
    return {
      workspace: this.workspace,
      builder: this.builder,
      currentPage: this.currentPage,
      mode,
      formulaComponent: ApplicationBuilderFormulaInput,
      applicationContext: this.applicationContext,
    }
  },

  /**
   * When the route is updated we want to unselect the element
   */
  beforeRouteUpdate(to, from, next) {
    // Unselect previously selected element
    const currentBuilder = this.$store.getters['application/get'](
      parseInt(from.params.builderId)
    )
    this.$store.dispatch('element/select', {
      builder: currentBuilder,
      element: null,
    })
    if (from.params.builderId !== to.params?.builderId) {
      // When we switch from one application to another we want to logoff the current
      // user
      if (currentBuilder) {
        // We want to reload once only data for this builder next time
        this.$store.dispatch('application/forceUpdate', {
          application: currentBuilder,
          data: { _loadedOnce: false },
        })
        this.$store.dispatch('userSourceUser/logoff', {
          application: currentBuilder,
        })
      }
    }
    next()
  },
  /**
   * When the user leaves to another page we want to unselect the selected page. This
   * way it will not be highlighted the left sidebar.
   */
  beforeRouteLeave(to, from, next) {
    this.$store.dispatch('page/unselect')

    const builder = this.$store.getters['application/get'](
      parseInt(from.params.builderId)
    )

    if (builder) {
      // Unselect previously selected element
      this.$store.dispatch('element/select', {
        builder,
        element: null,
      })
      // We want to reload once only data for this builder next time
      this.$store.dispatch('application/forceUpdate', {
        application: builder,
        data: { _loadedOnce: false },
      })
      this.$store.dispatch('userSourceUser/logoff', { application: builder })
    }

    next()
  },
  layout: 'app',
  async asyncData({ store, params, error, $registry, app }) {
    const builderId = parseInt(params.builderId)
    const pageId = parseInt(params.pageId)

    const data = { panelWidth: 360 }

    try {
      const builder = await store.dispatch('application/selectById', builderId)
      store.dispatch('userSourceUser/setCurrentApplication', {
        application: builder,
      })
      const workspace = await store.dispatch(
        'workspace/selectById',
        builder.workspace.id
      )

      const builderApplicationType = $registry.get(
        'application',
        BuilderApplicationType.getType()
      )

      const page = store.getters['page/getById'](builder, pageId)

      if (page.shared) {
        return error({
          statusCode: 404,
          message: app.i18n.t('pageEditor.pageNotFound'),
        })
      }

      await builderApplicationType.loadExtraData(builder, mode)

      await Promise.all([
        store.dispatch('dataSource/fetch', {
          page,
        }),
        store.dispatch('element/fetch', { builder, page }),
        store.dispatch('builderWorkflowAction/fetch', { page }),
      ])

      await DataProviderType.initAll($registry.getAll('builderDataProvider'), {
        builder,
        page,
        mode,
      })

      // And finally select the page to display it
      await store.dispatch('page/selectById', {
        builder,
        pageId,
      })

      data.workspace = workspace
      data.builder = builder
      data.currentPage = page
    } catch (e) {
      // In case of a network error we want to fail hard.
      if (e.response === undefined && !(e instanceof StoreItemLookupError)) {
        throw e
      }

      return error({
        statusCode: 404,
        message: app.i18n.t('pageEditor.pageNotFound'),
      })
    }

    return data
  },
  computed: {
    applicationContext() {
      return {
        workspace: this.workspace,
        builder: this.builder,
        mode,
      }
    },
    dataSources() {
      return this.$store.getters['dataSource/getPageDataSources'](
        this.currentPage
      )
    },
    sharedPage() {
      return this.$store.getters['page/getSharedPage'](this.builder)
    },
    sharedDataSources() {
      return this.$store.getters['dataSource/getPageDataSources'](
        this.sharedPage
      )
    },
    dispatchContext() {
      return DataProviderType.getAllDataSourceDispatchContext(
        this.$registry.getAll('builderDataProvider'),
        { ...this.applicationContext, page: this.currentPage }
      )
    },
    // Separate dispatch context for application level shared data sources
    // This one doesn't contain the page.
    applicationDispatchContext() {
      return DataProviderType.getAllDataSourceDispatchContext(
        this.$registry.getAll('builderDataProvider'),
        { builder: this.builder, mode }
      )
    },
  },
  watch: {
    dataSources: {
      deep: true,
      /**
       * Update data source content on data source configuration changes
       */
      handler() {
        this.$store.dispatch(
          'dataSourceContent/debouncedFetchPageDataSourceContent',
          {
            page: this.currentPage,
            data: this.dispatchContext,
            mode: this.mode,
          }
        )
      },
    },
    sharedDataSources: {
      deep: true,
      /**
       * Update shared data source content on data source configuration changes
       */
      handler() {
        this.$store.dispatch(
          'dataSourceContent/debouncedFetchPageDataSourceContent',
          {
            page: this.sharedPage,
            data: this.dispatchContext,
          }
        )
      },
    },
    dispatchContext: {
      deep: true,
      /**
       * Update data source content on backend context changes
       */
      handler(newDispatchContext, oldDispatchContext) {
        if (!_.isEqual(newDispatchContext, oldDispatchContext)) {
          this.$store.dispatch(
            'dataSourceContent/debouncedFetchPageDataSourceContent',
            {
              page: this.currentPage,
              data: newDispatchContext,
              mode: this.mode,
            }
          )
        }
      },
    },
    applicationDispatchContext: {
      deep: true,
      /**
       * Update data source content on backend context changes
       */
      handler(newDispatchContext, oldDispatchContext) {
        if (!_.isEqual(newDispatchContext, oldDispatchContext)) {
          this.$store.dispatch(
            'dataSourceContent/debouncedFetchPageDataSourceContent',
            {
              page: this.sharedPage,
              data: newDispatchContext,
            }
          )
        }
      },
    },
  },
}
</script>
