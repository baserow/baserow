import {
  defineNuxtRouteMiddleware,
  navigateTo,
  useNuxtApp,
  useRequestURL,
  useResponseHeader,
  useRuntimeConfig,
} from '#imports'

import { fetchPublicBuilder } from '@baserow/modules/builder/services/publishedBuilder'
import {
  getBuilderPreviewCookiePath,
  getBuilderPreviewUserSourceCookieName,
} from '@baserow/modules/builder/utils/preview'
import {
  setToken,
  userSourceCookieTokenName,
} from '@baserow/modules/core/utils/auth'

/** Removes callback credentials from a URL and any encoded next destination. */
const removeCallbackParams = (url, registry) => {
  for (const name of getAuthProviderCallbackParamNames(url, registry)) {
    url.searchParams.delete(name)
  }

  for (const next of url.searchParams.getAll('next')) {
    try {
      const decodedNext = decodeURIComponent(next)
      const nested = new URL(decodedNext, url.origin)
      const originalNested = nested.toString()
      removeCallbackParams(nested, registry)
      if (nested.toString() !== originalNested) {
        const cleaned = /^https?:\/\//i.test(decodedNext)
          ? nested.toString()
          : `${nested.pathname}${nested.search}${nested.hash}`
        url.searchParams.set(
          'next',
          decodedNext === next ? cleaned : encodeURIComponent(cleaned)
        )
      }
    } catch {
      // Keep malformed navigation values unchanged; only credentials are removed.
    }
  }
}

/** Returns callback parameters claimed by registered auth provider types. */
export const getAuthProviderCallbackParamNames = (url, registry) => {
  const providerTypes = Object.values(registry.getAll('appAuthProvider') || {})
  return [
    ...new Set(
      providerTypes.flatMap((providerType) =>
        providerType.getAuthProviderCallbackQueryParamNames(url)
      )
    ),
  ]
}

/** Returns the current router target using the request's trusted origin. */
export const getAuthProviderCallbackUrl = (to, requestUrl) =>
  new URL(to.fullPath, requestUrl.origin)

/** Returns the single callback accepted by one of the Builder's providers. */
export const getAuthProviderCallback = (
  url,
  builder,
  registry,
  callbackParamNames = getAuthProviderCallbackParamNames(url, registry)
) => {
  if (callbackParamNames.length !== 1) {
    return null
  }
  const callbacks = []
  for (const userSource of builder?.user_sources || []) {
    for (const authProvider of userSource.auth_providers) {
      const providerType = registry.get('appAuthProvider', authProvider.type)
      const callback = providerType.getAuthProviderCallback(userSource, url)
      if (callback?.token) {
        callbacks.push(callback)
      }
    }
  }
  return callbacks.length === 1 ? callbacks[0] : null
}

/** Returns a same-origin location with all callback credentials removed. */
export const getCleanCallbackLocation = (requestUrl, registry) => {
  const cleanUrl = new URL(requestUrl.toString())
  removeCallbackParams(cleanUrl, registry)
  return `${cleanUrl.pathname}${cleanUrl.search}${cleanUrl.hash}`
}

/** Installs a verified callback token before the public page is rendered. */
export default defineNuxtRouteMiddleware(async (to) => {
  const requestUrl = useRequestURL()
  const callbackUrl = getAuthProviderCallbackUrl(to, requestUrl)
  const nuxtApp = useNuxtApp()
  const callbackParamNames = getAuthProviderCallbackParamNames(
    callbackUrl,
    nuxtApp.$registry
  )
  if (callbackParamNames.length === 0) {
    return
  }

  const config = useRuntimeConfig()
  const cacheControlHeader = import.meta.server
    ? useResponseHeader('Cache-Control')
    : null
  const referrerPolicyHeader = import.meta.server
    ? useResponseHeader('Referrer-Policy')
    : null
  try {
    const builder = await fetchPublicBuilder(nuxtApp.$client, {
      mode: to.meta.builderPageMode,
      builderId: to.params.builderId ? Number(to.params.builderId) : null,
      domain: requestUrl.hostname,
    })
    const callback = getAuthProviderCallback(
      callbackUrl,
      builder,
      nuxtApp.$registry,
      callbackParamNames
    )
    if (callback) {
      const preview = to.meta.builderPageMode === 'preview'
      setToken(
        nuxtApp,
        callback.token,
        preview
          ? getBuilderPreviewUserSourceCookieName()
          : userSourceCookieTokenName,
        {
          sameSite: 'Lax',
          cookieUrl: preview
            ? config.public.builderPreviewUrl
            : config.public.publicWebFrontendUrl,
          path: preview ? getBuilderPreviewCookiePath(builder.id) : '/',
        }
      )
    }
  } catch {
    // Never retain callback credentials when builder verification fails.
  }

  if (cacheControlHeader && referrerPolicyHeader) {
    cacheControlHeader.value = 'no-store'
    referrerPolicyHeader.value = 'no-referrer'
  }
  return nuxtApp.runWithContext(() =>
    navigateTo(getCleanCallbackLocation(callbackUrl, nuxtApp.$registry), {
      redirectCode: 303,
    })
  )
})
