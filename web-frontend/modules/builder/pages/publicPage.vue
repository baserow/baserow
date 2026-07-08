<template>
  <PublicPageContent
    v-if="!pending && !error && asyncDataResult"
    :workspace="workspace"
    :builder="builder"
    :page="currentPage"
    :params="params"
    :path="path"
    :mode="pageMode"
  />
</template>

<script setup>
import { computed } from 'vue'
import { useStore } from 'vuex'
import { useAsyncData, useNuxtApp, navigateTo, createError } from '#app'
import { resolveApplicationRoute } from '@baserow/modules/builder/utils/routing'

import { DataProviderType } from '@baserow/modules/core/dataProviderTypes'
import _ from 'lodash'

import {
  getTokenIfEnoughTimeLeft,
  userSourceCookieTokenName,
} from '@baserow/modules/core/utils/auth'
import { useHead, useRequestURL, useRoute } from '#imports'
import PublicPageContent from '../components/PublicPageContent.vue'

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

const props = defineProps({
  builderId: {
    type: Number,
    required: false,
    default: null,
  },
  pathMatch: {
    type: String,
    required: false,
    default: null,
  },
  mode: {
    type: String,
    required: false,
    default: 'public',
  },
})

const store = useStore()
const route = useRoute()
const nuxtApp = useNuxtApp()

const { $registry, $i18n } = nuxtApp

const requestUrl = useRequestURL()
const requestHostname = requestUrl.hostname
const routeBuilderId = props.builderId
const routeMode =
  typeof route.meta.builderPageMode === 'string'
    ? route.meta.builderPageMode
    : null
const mode = routeMode || props.mode
const routePathMatch =
  props.pathMatch !== null
    ? props.pathMatch
    : Array.isArray(route.params.pathMatch)
      ? route.params.pathMatch.join('/')
      : route.params.pathMatch || ''

if (mode === 'preview') {
  useHead({
    titleTemplate: '',
    title: '',
  })

  store.dispatch('userSourceUser/setCurrentApplication', {
    application: null,
    mode,
  })
}

const {
  data: asyncDataResult,
  error,
  pending,
} = await useAsyncData(
  `publicPage_${requestHostname}_${route.fullPath}`,
  async () => {
    const query = route.query

    const builderId = routeBuilderId

    let builder = store.getters['application/getSelected']
    let needPostBuilderLoading = false

    if (!builder || (builderId && builderId !== builder.id)) {
      try {
        if (builderId) {
          // Legacy preview URLs have the builderId in the path.
          await store.dispatch('publicBuilder/fetchById', {
            builderId,
          })
          builder = await store.dispatch('application/selectById', builderId)
        } else if (mode === 'preview') {
          const { id: receivedBuilderId } = await store.dispatch(
            'publicBuilder/fetchPreview'
          )
          builder = await store.dispatch(
            'application/selectById',
            receivedBuilderId
          )
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
          message: $i18n.t('publicPage.siteNotFound'),
          data: {
            report: false,
          },
          fatal: true,
        })
      }

      needPostBuilderLoading = true
    }

    store.dispatch('userSourceUser/setCurrentApplication', {
      application: builder,
      mode,
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
            message: authError.message,
            data: {
              report: false,
            },
            fatal: true,
          })
        }
      }
    }

    const found = resolveApplicationRoute(
      store.getters['page/getVisiblePages'](builder),
      routePathMatch
    )

    // Handle 404
    if (!found) {
      throw createError({
        statusCode: 404,
        message: $i18n.t('publicPage.pageNotFound'),
        data: {
          report: false,
        },
        fatal: true,
      })
    }

    const [pageFound, path, pageParams] = found
    // Handle 404
    if (pageFound.shared) {
      throw createError({
        statusCode: 404,
        message: $i18n.t('publicPage.pageNotFound'),
        data: {
          report: false,
        },
        fatal: true,
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
        error.response?.data?.error === 'ERROR_PAGE_DOES_NOT_EXIST'
      ) {
        // This case is when you had a tab open on the site and the site has been
        // published in the meantime. Page IDs aren't valid anymore
        throw createError({
          statusCode: 404,
          statusMessage: $i18n.t('publicPage.pageNotFound'),
          data: {
            report: false,
          },
          fatal: true,
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
  },
  {
    server: mode !== 'preview',
  }
)

if (error.value) {
  throw error.value
}

const workspace = computed(() => asyncDataResult.value?.workspace)
const builder = computed(() => asyncDataResult.value?.builder)
const currentPage = computed(() => asyncDataResult.value?.currentPage)
const path = computed(() => asyncDataResult.value?.path)
const params = computed(() => asyncDataResult.value?.params)
const pageMode = computed(() => asyncDataResult.value?.mode)
</script>
