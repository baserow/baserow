<template>
  <div>
    <BuilderToasts></BuilderToasts>
    <RecursiveWrapper :components="builderPageDecorators">
      <PageContent
        v-if="canViewPage"
        :path="path"
        :params="params"
        :elements="elements"
        :shared-elements="sharedElements"
      />
    </RecursiveWrapper>
  </div>
</template>

<script>
import PageContent from '@baserow/modules/builder/components/page/PageContent'
import { resolveApplicationRoute } from '@baserow/modules/builder/utils/routing'

import { DataProviderType } from '@baserow/modules/core/dataProviderTypes'
import BuilderToasts from '@baserow/modules/builder/components/BuilderToasts'
import ApplicationBuilderFormulaInput from '@baserow/modules/builder/components/ApplicationBuilderFormulaInput'
import _ from 'lodash'
import { prefixInternalResolvedUrl } from '@baserow/modules/builder/utils/urlResolution'
import { userCanViewPage } from '@baserow/modules/builder/utils/visibility'

import {
  getTokenIfEnoughTimeLeft,
  userSourceCookieTokenName,
  setToken,
} from '@baserow/modules/core/utils/auth'
import { QUERY_PARAM_TYPE_HANDLER_FUNCTIONS } from '@baserow/modules/builder/enums'
import RecursiveWrapper from '@baserow/modules/core/components/RecursiveWrapper'
import { ThemeConfigBlockType } from '@baserow/modules/builder/themeConfigBlockTypes'

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
  name: 'PublicPage',
  components: { RecursiveWrapper, PageContent, BuilderToasts },
  provide() {
    return {
      workspace: this.workspace,
      builder: this.builder,
      currentPage: this.currentPage,
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
    redirect,
    route,
    query,
  }) {
    let mode = 'public'
    const builderId = params.builderId ? parseInt(params.builderId, 10) : null

    // We have a builderId parameter in the path so it's a preview
    if (builderId) {
      mode = 'preview'
    }

    let builder = store.getters['application/getSelected']
    let needPostBuilderLoading = false

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

      needPostBuilderLoading = true
    }
    store.dispatch('userSourceUser/setCurrentApplication', {
      application: builder,
    })

    if (
      (!process.server || req) &&
      !store.getters['userSourceUser/isAuthenticated'](builder)
    ) {
      const refreshToken = getTokenIfEnoughTimeLeft(
        app,
        userSourceCookieTokenName
      )
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

    if (needPostBuilderLoading) {
      // Post builder loading task executed once per application
      // It's executed here to make sure we are authenticated at that point
      const sharedPage = await store.getters['page/getSharedPage'](builder)
      await Promise.all([
        store.dispatch('dataSource/fetchPublished', {
          page: sharedPage,
        }),
        store.dispatch('element/fetchPublished', {
          builder,
          page: sharedPage,
        }),
        store.dispatch('builderWorkflowAction/fetchPublished', {
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

    // Auth providers can get error code from the URL parameters
    for (const userSource of builder.user_sources) {
      for (const authProvider of userSource.auth_providers) {
        const authError = $registry
          .get('appAuthProvider', authProvider.type)
          .handleError(userSource, authProvider, route)
        if (authError) {
          return error({
            statusCode: authError.code,
            message: authError.message,
          })
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

    const [pageFound, path, pageParams] = found
    // Handle 404
    if (pageFound.shared) {
      return error({
        statusCode: 404,
        message: app.i18n.t('publicPage.pageNotFound'),
      })
    }

    // Merge the query string values with the page parameters
    const pageParamsValue = Object.assign({}, query, pageParams)
    pageFound.query_params.forEach((queryParam) => {
      if (queryParam.name in pageParamsValue) {
        return
      }
      if (queryParam.type === 'text') {
        pageParamsValue[queryParam.name] = ''
      } else {
        pageParamsValue[queryParam.name] = null
      }
    })
    const page = await store.getters['page/getById'](builder, pageFound.id)

    try {
      await Promise.all([
        store.dispatch('dataSource/fetchPublished', {
          page,
        }),
        store.dispatch('element/fetchPublished', { builder, page }),
        store.dispatch('builderWorkflowAction/fetchPublished', { page }),
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

    if (!store.getters['auth/isAuthenticated']) {
      // It means that we are visiting a published website
      // We need to populate additional data for the user for license check later
      store.dispatch('auth/forceSetAdditionalData', {
        active_licenses: {
          per_workspace: {
            [builder.workspace.id]: Object.fromEntries(
              (builder.workspace.licenses || []).map((license) => [
                license,
                true,
              ])
            ),
          },
        },
      })
    }

    return {
      workspace: builder.workspace,
      builder,
      currentPage: page,
      path,
      params,
      mode,
    }
  },
  head() {
    const cssVars = Object.entries(this.themeStyle)
      .map(([key, value]) => `\n${key}: ${value};`)
      .join(' ')

    const header = {
      titleTemplate: '',
      title: this.currentPage.name,
      bodyAttrs: {
        class: 'public-page',
      },
      __dangerouslyDisableSanitizers: ['style'],
      style: [{ cssText: `:root { ${cssVars} }`, type: 'text/css' }],
    }

    if (this.faviconLink) {
      header.link = [this.faviconLink]
    }

    const pluginHeaders = this.$registry.getList('plugin').map((plugin) =>
      plugin.getBuilderApplicationHeaderAddition({
        builder: this.builder,
        mode: this.mode,
      })
    )

    const result = _.mergeWith(
      {},
      ...pluginHeaders,
      header,
      (objValue, srcValue, key, object, source, stack) => {
        switch (key) {
          case 'link':
          case 'script':
            if (_.isArray(objValue)) {
              return objValue.concat(srcValue)
            }
        }
        return undefined // Default merge action
      }
    )
    return result
  },
  computed: {
    themeConfigBlocks() {
      return this.$registry.getOrderedList('themeConfigBlock')
    },
    themeStyle() {
      return ThemeConfigBlockType.getAllStyles(
        this.themeConfigBlocks,
        this.builder.theme
      )
    },
    elements() {
      return this.$store.getters['element/getRootElements'](this.currentPage)
    },
    builderPageDecorators() {
      // Get available page decorators from registry
      return Object.values(this.$registry.getAll('builderPageDecorator') || {})
        .filter((decorator) => decorator.isDecorationAllowed(this.workspace))
        .map((decorator) => ({
          component: decorator.component,
          props: decorator.getProps(),
        }))
    },
    applicationContext() {
      return {
        workspace: this.workspace,
        builder: this.builder,
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
        this.currentPage
      )
    },
    dispatchContext() {
      return DataProviderType.getAllDataSourceDispatchContext(
        this.$registry.getAll('builderDataProvider'),
        { ...this.applicationContext, page: this.currentPage }
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
    sharedElements() {
      return this.$store.getters['element/getRootElements'](this.sharedPage)
    },
    isAuthenticated() {
      return this.$store.getters['userSourceUser/isAuthenticated'](this.builder)
    },
    faviconLink() {
      if (this.builder.favicon_file?.url) {
        return {
          rel: 'icon',
          type: this.builder.favicon_file.mime_type,
          href: this.builder.favicon_file.url,
          sizes: '128x128',
          hid: true,
        }
      }

      return null
    },
  },
  watch: {
    '$route.query': {
      immediate: true,
      deep: true,
      handler(newQuery) {
        // when query string changed due to user action,
        // update the page's query parameters in the store
        Promise.all(
          this.currentPage.query_params.map(({ name, type }) => {
            let value
            try {
              if (newQuery[name]) {
                value = QUERY_PARAM_TYPE_HANDLER_FUNCTIONS[type](newQuery[name])
              }
            } catch {
              // Skip setting the parameter if the user-provided value
              // doesn't pass our parameter `type` validation.
              return null
            }
            return this.$store.dispatch('pageParameter/setParameter', {
              page: this.currentPage,
              name,
              value,
            })
          })
        )
      },
    },
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
       * Update data source content on dispatch context changes
       */
      handler(newDispatchContext, oldDispatchContext) {
        if (!_.isEqual(newDispatchContext, oldDispatchContext)) {
          this.$store.dispatch(
            'dataSourceContent/debouncedFetchPageDataSourceContent',
            {
              page: this.sharedPage,
              data: newDispatchContext,
              mode: this.mode,
            }
          )
        }
      },
    },
    async isAuthenticated(newIsAuthenticated) {
      // When the user login or logout, we need to refetch the elements and actions
      // as they might have changed
      await Promise.all([
        this.$store.dispatch('dataSource/fetchPublished', {
          page: this.sharedPage,
        }),
        this.$store.dispatch('dataSource/fetchPublished', {
          page: this.currentPage,
        }),
        this.$store.dispatch('element/fetchPublished', {
          builder: this.builder,
          page: this.sharedPage,
        }),
        this.$store.dispatch('element/fetchPublished', {
          builder: this.builder,
          page: this.currentPage,
        }),
        this.$store.dispatch('builderWorkflowAction/fetchPublished', {
          page: this.currentPage,
        }),
        this.$store.dispatch('builderWorkflowAction/fetchPublished', {
          page: this.sharedPage,
        }),
      ])

      if (newIsAuthenticated) {
        // If the user has just logged in, we redirect him to the next page.
        await this.maybeRedirectToNextPage()
      } else {
        // If the user is on a hidden page, redirect them to the Login page if possible.
        await this.maybeRedirectUserToLoginPage()
      }
    },
  },
  async mounted() {
    await this.checkProviderAuthentication()
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

        const currentPath = this.$route.fullPath
        if (url !== currentPath) {
          this.$store.dispatch('builderToast/info', {
            title: this.$t('publicPage.authorizedToastTitle'),
            message: this.$t('publicPage.authorizedToastMessage'),
          })
          const nextPath = encodeURIComponent(currentPath)
          this.$router.push({ path: url, query: { next: nextPath } })
        }
      }
    },
    maybeRedirectToNextPage() {
      if (this.$route.query.next) {
        const decodedNext = decodeURIComponent(this.$route.query.next)
        this.$router.push(decodedNext)
      }
    },
    async checkProviderAuthentication() {
      // Iterate over all auth providers to check if one can get a refresh token
      let refreshTokenFromProvider = null

      for (const userSource of this.builder.user_sources) {
        for (const authProvider of userSource.auth_providers) {
          refreshTokenFromProvider = this.$registry
            .get('appAuthProvider', authProvider.type)
            .getAuthToken(userSource, authProvider, this.$route)
          if (refreshTokenFromProvider) {
            break
          }
        }
        if (refreshTokenFromProvider) {
          break
        }
      }

      if (refreshTokenFromProvider) {
        setToken(this, refreshTokenFromProvider, userSourceCookieTokenName, {
          sameSite: 'Lax',
        })
        try {
          await this.$store.dispatch('userSourceUser/refreshAuth', {
            application: this.builder,
            token: refreshTokenFromProvider,
          })
          this.$store.dispatch('builderToast/info', {
            title: this.$t('publicPage.loginToastTitle'),
            message: this.$t('publicPage.loginToastMessage'),
          })
        } catch (error) {
          if (error.response?.status === 401) {
            // We logoff as the token has probably expired or became invalid
            logOffAndReturnToLogin({
              builder: this.builder,
              store: this.$store,
              redirect: (...args) => this.$router.push(...args),
            })
          } else {
            throw error
          }
        }
      }
    },
  },
}
</script>
