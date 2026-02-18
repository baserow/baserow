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
import { useHead, useNuxtApp } from '#app'
import PageContent from '@baserow/modules/builder/components/page/PageContent'

import { DataProviderType } from '@baserow/modules/core/dataProviderTypes'
import BuilderToasts from '@baserow/modules/builder/components/BuilderToasts'
import ApplicationBuilderFormulaInput from '@baserow/modules/builder/components/ApplicationBuilderFormulaInput'
import _ from 'lodash'
import { prefixInternalResolvedUrl } from '@baserow/modules/builder/utils/urlResolution'
import { userCanViewPage } from '@baserow/modules/builder/utils/visibility'

import {
  userSourceCookieTokenName,
  setToken,
} from '@baserow/modules/core/utils/auth'
import { QUERY_PARAM_TYPE_HANDLER_FUNCTIONS } from '@baserow/modules/builder/enums'
import RecursiveWrapper from '@baserow/modules/core/components/RecursiveWrapper'
import { ThemeConfigBlockType } from '@baserow/modules/builder/themeConfigBlockTypes'
import { useRoute, useRouter } from '#imports'

defineOptions({
  name: 'PublicPageContent',
})

const store = useStore()
const route = useRoute()
const router = useRouter()
const nuxtApp = useNuxtApp()

const { $registry, $i18n } = nuxtApp

const props = defineProps({
  workspace: {
    type: Object,
    required: true,
  },
  builder: {
    type: Object,
    required: true,
  },
  page: {
    type: Object,
    required: true,
  },
  params: {
    type: Object,
    required: true,
  },
  path: {
    type: String,
    required: true,
  },
  mode: {
    type: String,
    required: true,
  },
})

provide('workspace', props.workspace)
provide('builder', props.builder)
provide('currentPage', props.page)
provide('mode', props.mode)
provide('formulaComponent', ApplicationBuilderFormulaInput)
provide(
  'applicationContext',
  computed(() => applicationContext.value)
)

const elements = computed(() => {
  return store.getters['element/getRootElements'](props.page)
})

const builderPageDecorators = computed(() => {
  // Get available page decorators from registry
  return Object.values($registry.getAll('builderPageDecorator') || {})
    .filter((decorator) => decorator.isDecorationAllowed(props.workspace))
    .map((decorator) => ({
      component: decorator.component,
      props: decorator.getProps(),
    }))
})

const applicationContext = computed(() => ({
  workspace: props.workspace,
  builder: props.builder,
  pageParamsValue: props.params,
  mode: props.mode,
}))

const dispatchContext = computed(() =>
  DataProviderType.getAllDataSourceDispatchContext(
    $registry.getAll('builderDataProvider'),
    { ...applicationContext.value, page: props.page }
  )
)

// Separate dispatch context for application level data sources
const applicationDispatchContext = computed(() =>
  DataProviderType.getAllDataSourceDispatchContext(
    $registry.getAll('builderDataProvider'),
    { builder: props.builder, mode: props.mode }
  )
)

const sharedPage = computed(() =>
  store.getters['page/getSharedPage'](props.builder)
)

const sharedElements = computed(() =>
  store.getters['element/getRootElements'](sharedPage.value)
)

const isAuthenticated = computed(() =>
  store.getters['userSourceUser/isAuthenticated'](props.builder)
)

const faviconLink = computed(() => {
  if (props.builder.favicon_file?.url) {
    return {
      rel: 'icon',
      type: props.builder.favicon_file.mime_type,
      href: props.builder.favicon_file.url,
      sizes: '128x128',
      hid: true,
    }
  }
  return null
})

const themeConfigBlocks = computed(() =>
  $registry.getOrderedList('themeConfigBlock')
)

const themeStyle = computed(() =>
  ThemeConfigBlockType.getAllStyles(
    themeConfigBlocks.value,
    props.builder.theme
  )
)

const headConfig = computed(() => {
  const cssVars = Object.entries(themeStyle.value)
    .map(([key, value]) => `\n${key}: ${value};`)
    .join(' ')

  const header = {
    titleTemplate: '',
    title: props.page.name,
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
      builder: props.builder,
      mode: props.mode,
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

watch(
  () => route.query,
  (newQuery) => {
    // when query string changed due to user action,
    // update the page's query parameters in the store
    Promise.all(
      props.page.query_params.map(({ name, type }) => {
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
          page: props.page,
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
        page: props.page,
        data: newDispatchContext,
        mode: props.mode,
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
        mode: props.mode,
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
        page: props.page,
      }),
      store.dispatch('element/fetchPublished', {
        builder: props.builder,
        page: sharedPage.value,
      }),
      store.dispatch('element/fetchPublished', {
        builder: props.builder,
        page: props.page,
      }),
      store.dispatch('builderWorkflowAction/fetchPublished', {
        page: props.page,
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

onMounted(async () => {
  await checkProviderAuthentication()
  await maybeRedirectUserToLoginPage()
})

/**
 * Returns true if the current user is allowed to view this page,
 * otherwise returns false.
 */
const canViewPage = computed(() =>
  userCanViewPage(
    store.getters['userSourceUser/getUser'](props.builder),
    store.getters['userSourceUser/isAuthenticated'](props.builder),
    props.page
  )
)

/**
 * If the user does not have access to the current page, redirect them to
 * the Login page if possible.
 */
const maybeRedirectUserToLoginPage = async () => {
  if (!canViewPage.value && props.builder.login_page_id) {
    const loginPage = await store.getters['page/getById'](
      props.builder,
      props.builder.login_page_id
    )
    const url = prefixInternalResolvedUrl(
      loginPage.path,
      props.builder,
      'page',
      props.mode
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

const checkProviderAuthentication = async () => {
  // Iterate over all auth providers to check if one can get a refresh token
  let refreshTokenFromProvider = null

  for (const userSource of props.builder.user_sources) {
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
        application: props.builder,
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
          builder: props.builder,
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
