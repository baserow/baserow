<template>
  <div>
    <BuilderToasts />
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

<script setup>
import { computed, watch, onMounted, provide } from 'vue'
import { useStore } from 'vuex'
import {
  useAsyncData,
  useHead,
  useNuxtApp,
  navigateTo,
  createError,
} from '#app'
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
import { useRoute, useRouter } from '#imports'

const logOffAndReturnToLogin = async ({ builder, store, redirect }) => {
  await store.dispatch('userSourceUser/logoff', {
    application: builder,
  })
  // Redirect to home page after logout
  return redirect({
    name: 'application-builder-page',
    params: { pathMatch: '/' },
  })
}

defineOptions({
  name: 'PublicPage',
})

const store = useStore()
const route = useRoute()
const router = useRouter()
const nuxtApp = useNuxtApp()

const { $registry, $i18n } = nuxtApp

const requestHostname = useRequestURL().hostname

const { data: asyncDataResult, error } = await useAsyncData(
  `publicPage_${requestHostname}_${route.fullPath}`,
  async () => {
    let mode = 'public'
    const query = route.query

    const builderId = route.params.builderId
      ? parseInt(route.params.builderId, 10)
      : null

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
          const { id: receivedBuilderId } = await store.dispatch(
            'publicBuilder/fetchByDomain',
            {
              domain: requestHostname,
            }
          )
          builder = await store.dispatch(
            'application/selectById',
            receivedBuilderId
          )
        }
      } catch (e) {
        throw createError({
          statusCode: 404,
          statusMessage: $i18n.t('publicPage.siteNotFound'),
        })
      }

      needPostBuilderLoading = true
    }

    store.dispatch('userSourceUser/setCurrentApplication', {
      application: builder,
    })

    if (
      (!import.meta.server || import.meta.server) &&
      !store.getters['userSourceUser/isAuthenticated'](builder)
    ) {
      const refreshToken = await getTokenIfEnoughTimeLeft(
        nuxtApp,
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
            await logOffAndReturnToLogin({
              builder,
              store,
              redirect: navigateTo,
            })
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
          throw createError({
            statusCode: authError.code,
            statusMessage: authError.message,
          })
        }
      }
    }

    const found = resolveApplicationRoute(
      store.getters['page/getVisiblePages'](builder),
      Array.isArray(route.params.pathMatch)
        ? route.params.pathMatch.join('/')
        : route.params.pathMatch
    )

    // Handle 404
    if (!found) {
      throw createError({
        statusCode: 404,
        statusMessage: $i18n.t('publicPage.pageNotFound'),
      })
    }

    const [pageFound, path, pageParams] = found
    // Handle 404
    if (pageFound.shared) {
      throw createError({
        statusCode: 404,
        statusMessage: $i18n.t('publicPage.pageNotFound'),
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
        await logOffAndReturnToLogin({ builder, store, redirect: navigateTo })
      } else if (
        error.response?.status === 404 &&
        error.response?.data?.error === 'ERROR_PAGE_NOT_FOUND'
      ) {
        // This case is when you had a tab open on the site and the site has been
        // published in the meantime. Page IDs aren't valid anymore
        throw createError({
          statusCode: 404,
          statusMessage: $i18n.t('publicPage.pageNotFound'),
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

    // And finally select the page to display it
    // It is useful for realtime events.
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
      params: pageParams,
      path,
      mode,
    }
  }
)

if (error.value) {
  // If we have an error we want to display it.
  throw error.value
}

const workspace = computed(() => asyncDataResult.value.workspace)
const builder = computed(() => asyncDataResult.value.builder)
const currentPage = computed(() => asyncDataResult.value.currentPage)
const path = computed(() => asyncDataResult.value.path)
const params = computed(() => asyncDataResult.value.params)
const mode = computed(() => asyncDataResult.value.mode)

provide('workspace', workspace.value)
provide('builder', builder.value)
provide('currentPage', currentPage.value)
provide('mode', mode.value)
provide('formulaComponent', ApplicationBuilderFormulaInput)
provide(
  'applicationContext',
  computed(() => applicationContext.value)
)

const themeConfigBlocks = computed(() =>
  $registry.getOrderedList('themeConfigBlock')
)

const themeStyle = computed(() =>
  ThemeConfigBlockType.getAllStyles(
    themeConfigBlocks.value,
    builder.value.theme
  )
)

const elements = computed(() => {
  if (!currentPage.value) {
    return []
  }
  return store.getters['element/getRootElements'](currentPage.value)
})

const builderPageDecorators = computed(() => {
  // Get available page decorators from registry
  return Object.values($registry.getAll('builderPageDecorator') || {})
    .filter((decorator) => decorator.isDecorationAllowed(workspace.value))
    .map((decorator) => ({
      component: decorator.component,
      props: decorator.getProps(),
    }))
})

const applicationContext = computed(() => ({
  workspace: workspace.value,
  builder: builder.value,
  pageParamsValue: params.value,
  mode: mode.value,
}))

/**
 * Returns true if the current user is allowed to view this page,
 * otherwise returns false.
 */
const canViewPage = computed(() =>
  userCanViewPage(
    store.getters['userSourceUser/getUser'](builder.value),
    store.getters['userSourceUser/isAuthenticated'](builder.value),
    currentPage.value
  )
)

const dispatchContext = computed(() =>
  DataProviderType.getAllDataSourceDispatchContext(
    $registry.getAll('builderDataProvider'),
    { ...applicationContext.value, page: currentPage.value }
  )
)

// Separate dispatch context for application level data sources
const applicationDispatchContext = computed(() =>
  DataProviderType.getAllDataSourceDispatchContext(
    $registry.getAll('builderDataProvider'),
    { builder: builder.value, mode: mode.value }
  )
)

const sharedPage = computed(() =>
  store.getters['page/getSharedPage'](builder.value)
)

const sharedElements = computed(() =>
  store.getters['element/getRootElements'](sharedPage.value)
)

const isAuthenticated = computed(() =>
  store.getters['userSourceUser/isAuthenticated'](builder.value)
)

const faviconLink = computed(() => {
  if (builder.value.favicon_file?.url) {
    return {
      rel: 'icon',
      type: builder.value.favicon_file.mime_type,
      href: builder.value.favicon_file.url,
      sizes: '128x128',
      hid: true,
    }
  }
  return null
})

/**
 * head() -> useHead
 */
const headConfig = computed(() => {
  const cssVars = Object.entries(themeStyle.value)
    .map(([key, value]) => `\n${key}: ${value};`)
    .join(' ')

  const header = {
    titleTemplate: '',
    title: currentPage.value.name,
    bodyAttrs: {
      class: 'public-page',
    },
    style: [{ children: `:root { ${cssVars} }`, type: 'text/css' }],
  }

  if (faviconLink.value) {
    header.link = [faviconLink.value]
  }

  const pluginHeaders = $registry.getList('plugin').map((plugin) =>
    plugin.getBuilderApplicationHeaderAddition({
      builder: builder.value,
      mode: mode.value,
    })
  )

  const result = _.mergeWith(
    {},
    ...pluginHeaders,
    header,
    (objValue, srcValue, key) => {
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
})

useHead(headConfig)

/**
 * WATCHERS
 */

watch(
  () => route.query,
  (newQuery) => {
    // when query string changed due to user action,
    // update the page's query parameters in the store
    if (!currentPage.value) return
    Promise.all(
      currentPage.value.query_params.map(({ name, type }) => {
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
        return store.dispatch('pageParameter/setParameter', {
          page: currentPage.value,
          name,
          value,
        })
      })
    )
  },
  { immediate: true, deep: true }
)

watch(
  () => dispatchContext.value,
  (newDispatchContext, oldDispatchContext) => {
    /**
     * Update data source content on dispatch context changes
     */
    if (!_.isEqual(newDispatchContext, oldDispatchContext)) {
      store.dispatch('dataSourceContent/debouncedFetchPageDataSourceContent', {
        page: currentPage.value,
        data: newDispatchContext,
        mode: mode.value,
      })
    }
  },
  { deep: true }
)

watch(
  () => applicationDispatchContext.value,
  (newDispatchContext, oldDispatchContext) => {
    /**
     * Update data source content on dispatch context changes
     */
    if (!_.isEqual(newDispatchContext, oldDispatchContext)) {
      store.dispatch('dataSourceContent/debouncedFetchPageDataSourceContent', {
        page: sharedPage.value,
        data: newDispatchContext,
        mode: mode.value,
      })
    }
  },
  { deep: true }
)

watch(
  () => isAuthenticated.value,
  async (newIsAuthenticated) => {
    // When the user login or logout, we need to refetch the elements and actions
    // as they might have changed
    await Promise.all([
      store.dispatch('dataSource/fetchPublished', {
        page: sharedPage.value,
      }),
      store.dispatch('dataSource/fetchPublished', {
        page: currentPage.value,
      }),
      store.dispatch('element/fetchPublished', {
        builder: builder.value,
        page: sharedPage.value,
      }),
      store.dispatch('element/fetchPublished', {
        builder: builder.value,
        page: currentPage.value,
      }),
      store.dispatch('builderWorkflowAction/fetchPublished', {
        page: currentPage.value,
      }),
      store.dispatch('builderWorkflowAction/fetchPublished', {
        page: sharedPage.value,
      }),
    ])

    if (newIsAuthenticated) {
      // If the user has just logged in, we redirect him to the next page.
      await maybeRedirectToNextPage()
    } else {
      // If the user is on a hidden page, redirect them to the Login page if possible.
      await maybeRedirectUserToLoginPage()
    }
  }
)

/**
 * LIFECYCLE
 */
onMounted(async () => {
  await checkProviderAuthentication()
  await maybeRedirectUserToLoginPage()
})

/**
 * METHODS -> fonctions
 */

/**
 * If the user does not have access to the current page, redirect them to
 * the Login page if possible.
 */
const maybeRedirectUserToLoginPage = async () => {
  if (!canViewPage.value && builder.value.login_page_id) {
    const loginPage = await store.getters['page/getById'](
      builder.value,
      builder.value.login_page_id
    )
    const url = prefixInternalResolvedUrl(
      loginPage.path,
      builder.value,
      'page',
      mode.value
    )

    const currentPath = route.fullPath
    if (url !== currentPath) {
      store.dispatch('builderToast/info', {
        title: $i18n.t('publicPage.authorizedToastTitle'),
        message: $i18n.t('publicPage.authorizedToastMessage'),
      })
      const nextPath = encodeURIComponent(currentPath)
      await router.push({ path: url, query: { next: nextPath } })
    }
  }
}

const maybeRedirectToNextPage = async () => {
  if (route.query.next) {
    const decodedNext = decodeURIComponent(route.query.next)
    await router.push(decodedNext)
  }
}

const checkProviderAuthentication = async () => {
  // Iterate over all auth providers to check if one can get a refresh token
  let refreshTokenFromProvider = null

  for (const userSource of builder.value.user_sources) {
    for (const authProvider of userSource.auth_providers) {
      refreshTokenFromProvider = $registry
        .get('appAuthProvider', authProvider.type)
        .getAuthToken(userSource, authProvider, route)
      if (refreshTokenFromProvider) {
        break
      }
    }
    if (refreshTokenFromProvider) {
      break
    }
  }

  if (refreshTokenFromProvider) {
    setToken(nuxtApp, refreshTokenFromProvider, userSourceCookieTokenName, {
      sameSite: 'Lax',
    })
    try {
      await store.dispatch('userSourceUser/refreshAuth', {
        application: builder.value,
        token: refreshTokenFromProvider,
      })
      store.dispatch('builderToast/info', {
        title: $i18n.t('publicPage.loginToastTitle'),
        message: $i18n.t('publicPage.loginToastMessage'),
      })
    } catch (error) {
      if (error.response?.status === 401) {
        // We logoff as the token has probably expired or became invalid
        await logOffAndReturnToLogin({
          builder: builder.value,
          store,
          redirect: (...args) => router.push(...args),
        })
      } else {
        throw error
      }
    }
  }
}
</script>
