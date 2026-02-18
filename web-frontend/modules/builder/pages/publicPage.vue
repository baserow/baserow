<template>
  <PublicPageContent
    v-if="!pending && !error"
    :workspace="workspace"
    :builder="builder"
    :page="currentPage"
    :params="params"
    :path="path"
    :mode="mode"
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
import { useRoute, useRouter } from '#imports'
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

const store = useStore()
const route = useRoute()
const nuxtApp = useNuxtApp()

const { $registry, $i18n } = nuxtApp

const requestHostname = useRequestURL().hostname

const {
  data: asyncDataResult,
  error,
  pending,
} = await useAsyncData(
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
  if (error.value.statusCode === 404) {
    showError(error.value)
  } else {
    throw error.value
  }
}

const workspace = computed(() => asyncDataResult.value?.workspace)
const builder = computed(() => asyncDataResult.value?.builder)
const currentPage = computed(() => asyncDataResult.value?.currentPage)
const path = computed(() => asyncDataResult.value?.path)
const params = computed(() => asyncDataResult.value?.params)
const mode = computed(() => asyncDataResult.value?.mode)
</script>
