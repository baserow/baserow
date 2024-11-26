<template>
  <div>
    <Toasts></Toasts>
    <PageContent
      v-if="canViewPage"
      :page="page"
      :path="path"
      :params="params"
      :elements="elements"
    />
  </div>
</template>

<script>
import PageContent from '@baserow/modules/builder/components/page/PageContent'
import { resolveApplicationRoute } from '@baserow/modules/builder/utils/routing'

import { DataProviderType } from '@baserow/modules/core/dataProviderTypes'
import Toasts from '@baserow/modules/core/components/toasts/Toasts'
import ApplicationBuilderFormulaInput from '@baserow/modules/builder/components/ApplicationBuilderFormulaInput'
import _ from 'lodash'
import { prefixInternalResolvedUrl } from '@baserow/modules/builder/utils/urlResolution'
import { userCanViewPage } from '@baserow/modules/builder/utils/visibility'

import {
  getTokenIfEnoughTimeLeft,
  setToken,
  userSourceCookieTokenName,
} from '@baserow/modules/core/utils/auth'

const logOffAndReturnToLogin = async ({ builder, store, redirect }) => {
  await store.dispatch('userSourceUser/logoff', {
    application: builder,
  })
  // Redirect to home page after logout
  await redirect({
    name: 'application-builder-page',
    params: { pathMatch: '/' },
  })
}

export default {
  components: { PageContent, Toasts },
  provide() {
    return {
      workspace: this.workspace,
      builder: this.builder,
      page: this.page,
      mode: this.mode,
      formulaComponent: ApplicationBuilderFormulaInput,
      applicationContext: this.applicationContext,
    }
  },

  async asyncData({
    store,
    params,
    error,
    $registry,
    app,
    req,
    route,
    redirect,
  }) {
    let mode = 'public'
    const builderId = params.builderId ? parseInt(params.builderId, 10) : null

    // We have a builderId parameter in the path so it's a preview
    if (builderId) {
      mode = 'preview'
    }

    let builder = store.getters['application/getSelected']

    if (!builder || (builderId && builderId !== builder.id)) {
      try {
        if (builderId) {
          // We have the builderId in the params so this is a preview
          // Must fetch the builder instance by this Id.
          await store.dispatch('publicBuilder/fetchById', {
            builderId,
          })
          builder = await store.dispatch('application/selectById', builderId)
        } else {
          // We don't have the builderId so it's a public page.
          // Must fetch the builder instance by domain name.
          const host = process.server ? req.headers.host : window.location.host
          const domain = new URL(`http://${host}`).hostname

          const { id: receivedBuilderId } = await store.dispatch(
            'publicBuilder/fetchByDomain',
            {
              domain,
            }
          )
          builder = await store.dispatch(
            'application/selectById',
            receivedBuilderId
          )
        }
      } catch (e) {
        return error({
          statusCode: 404,
          message: app.i18n.t('publicPage.siteNotFound'),
        })
      }

      // Post builder loading task executed once per application
      const sharedPage = await store.getters['page/getSharedPage'](builder)
      await Promise.all([
        store.dispatch('dataSource/fetchPublished', {
          page: sharedPage,
        }),
      ])

      await DataProviderType.initOnceAll(
        $registry.getAll('builderDataProvider'),
        {
          builder,
          mode,
        }
      )
    }
    store.dispatch('userSourceUser/setCurrentApplication', {
      application: builder,
    })

    if (
      (!process.server || req) &&
      !store.getters['userSourceUser/isAuthenticated'](builder)
    ) {
      // token can be in the query string (SSO) or in the cookies (previous session)
      let refreshToken = route.query.token
      if (refreshToken) {
        setToken(app, refreshToken, userSourceCookieTokenName, {
          sameSite: 'Lax',
        })
      } else {
        refreshToken = getTokenIfEnoughTimeLeft(app, userSourceCookieTokenName)
      }

      if (refreshToken) {
        try {
          await store.dispatch('userSourceUser/refreshAuth', {
            application: builder,
            token: refreshToken,
          })
        } catch (error) {
          if (error.response?.status === 401) {
            // We logoff as the token has probably expired or became invalid
            logOffAndReturnToLogin({ builder, store, redirect })
          } else {
            throw error
          }
        }
      }
    }

    const found = resolveApplicationRoute(
      store.getters['page/getVisiblePages'](builder),
      params.pathMatch
    )

    // Handle 404
    if (!found) {
      return error({
        statusCode: 404,
        message: app.i18n.t('publicPage.pageNotFound'),
      })
    }

    const [pageFound, path, pageParamsValue] = found

    const page = await store.getters['page/getById'](builder, pageFound.id)

    try {
      await Promise.all([
        store.dispatch('dataSource/fetchPublished', {
          page,
        }),
        store.dispatch('element/fetchPublished', { page }),
        store.dispatch('workflowAction/fetchPublished', { page }),
      ])
    } catch (error) {
      if (error.response?.status === 401) {
        // this case can happen if the site has been published with changes in the
        // user source. In this case we want to unlog the user.
        logOffAndReturnToLogin({ builder, store, redirect })
      } else if (
        error.response?.status === 404 &&
        error.response?.data?.error === 'ERROR_PAGE_NOT_FOUND'
      ) {
        // This case is when you had a tab open on the site and the site has been
        // published in the meantime. Page IDs aren't valid anymore
        return error({
          statusCode: 404,
          message: app.i18n.t('publicPage.pageNotFound'),
        })
      } else {
        throw error
      }
    }

    await DataProviderType.initAll($registry.getAll('builderDataProvider'), {
      builder,
      page,
      pageParamsValue,
      mode,
    })

    // TODO: This doesn't appear to be doing anything...
    // And finally select the page to display it
    await store.dispatch('page/selectById', {
      builder,
      pageId: pageFound.id,
    })

    return {
      builder,
      page,
      path,
      params,
      mode,
    }
  },
  head() {
    return {
      titleTemplate: '',
      title: this.page.name,
      bodyAttrs: {
        class: 'public-page',
      },
      link: this.faviconLink,
    }
  },
  computed: {
    elements() {
      return this.$store.getters['element/getRootElements'](this.page)
    },
    applicationContext() {
      return {
        builder: this.builder,
        page: this.page,
        pageParamsValue: this.params,
        mode: this.mode,
      }
    },
    /**
     * Returns true if the current user is allowed to view this page,
     * otherwise returns false.
     */
    canViewPage() {
      return userCanViewPage(
        this.$store.getters['userSourceUser/getUser'](this.builder),
        this.$store.getters['userSourceUser/isAuthenticated'](this.builder),
        this.page
      )
    },
    dispatchContext() {
      return DataProviderType.getAllDataSourceDispatchContext(
        this.$registry.getAll('builderDataProvider'),
        this.applicationContext
      )
    },
    // Separate dispatch context for application level data sources
    applicationDispatchContext() {
      return DataProviderType.getAllDataSourceDispatchContext(
        this.$registry.getAll('builderDataProvider'),
        { builder: this.builder, mode: this.mode }
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
    isAuthenticated() {
      return this.$store.getters['userSourceUser/isAuthenticated'](this.builder)
    },
    faviconLink() {
      if (this.builder.favicon_file?.url) {
        return [
          {
            rel: 'icon',
            type: this.builder.favicon_file.mime_type,
            href: this.builder.favicon_file.url,
            sizes: '128x128',
            hid: true,
          },
        ]
      } else {
        return []
      }
    },
  },
  watch: {
    dispatchContext: {
      deep: true,
      /**
       * Update data source content on dispatch context changes
       */
      handler(newDispatchContext, oldDispatchContext) {
        if (!_.isEqual(newDispatchContext, oldDispatchContext)) {
          this.$store.dispatch(
            'dataSourceContent/debouncedFetchPageDataSourceContent',
            {
              page: this.page,
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
       * Update data source content on dispatch context changes
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
    async isAuthenticated() {
      // When the user logs in or out, we need to refetch the elements and actions
      // as they might have changed.
      this.$store.dispatch('element/fetchPublished', { page: this.page })
      this.$store.dispatch('workflowAction/fetchPublished', { page: this.page })

      // If the user is on a hidden page, redirect them to the Login page if possible.
      await this.maybeRedirectUserToLoginPage()
    },
  },
  async mounted() {
    await this.maybeRedirectUserToLoginPage()
  },
  methods: {
    /**
     * If the user does not have access to the current page, redirect them to
     * the Login page if possible.
     */
    async maybeRedirectUserToLoginPage() {
      if (!this.canViewPage && this.builder.login_page_id) {
        const loginPage = await this.$store.getters['page/getById'](
          this.builder,
          this.builder.login_page_id
        )
        const url = prefixInternalResolvedUrl(
          loginPage.path,
          this.builder,
          'page',
          this.mode
        )

        if (url !== this.$router.history.current?.fullPath) {
          this.$router.push(url)
        }
      }
    },
  },
}
</script>
