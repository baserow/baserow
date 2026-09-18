import {
  defineEventHandler,
  getRequestURL,
  getCookie,
  sendRedirect,
  setCookie,
  setResponseHeader,
} from 'h3'
import { $fetch } from 'ofetch'
import { useRuntimeConfig } from 'nitropack/runtime'
import {
  getCookieName,
  getTokenCookieOptions,
  userSourceCookieTokenName,
} from '@baserow/modules/core/utils/cookie'
import { consumeUserSourceCallback } from '@baserow/modules/core/utils/userSourceCallback'
import {
  getBuilderPreviewCookiePath,
  getBuilderPreviewCookieName,
  getBuilderPreviewSsrCookieName,
  getBuilderPreviewUserSourceCookieName,
} from '@baserow/modules/builder/utils/preview'

// Consume the backend callback before Nuxt renders the public page or its payload.
export default defineEventHandler(async (event) => {
  const callback = consumeUserSourceCallback(getRequestURL(event))
  if (!callback) {
    return
  }

  const config = useRuntimeConfig(event)
  const previewBuilderId = callback.url.pathname.match(
    /^\/builder\/preview\/(\d+)(?:\/|$)/
  )?.[1]
  const isFrontendHost = [
    config.public.builderPreviewUrl,
    config.public.publicWebFrontendUrl,
  ].some((url) => url && new URL(url).hostname === callback.url.hostname)
  const isPreview = previewBuilderId && isFrontendHost
  let configuredProvider = false
  if (callback.token) {
    const publishedBuilderId = isFrontendHost
      ? callback.url.pathname.match(/^\/builder\/published\/(\d+)(?:\/|$)/)?.[1]
      : null
    const path = isPreview
      ? `builder/preview/${previewBuilderId}/current/`
      : publishedBuilderId
        ? `builder/domains/published/by_id/${publishedBuilderId}/`
        : `builder/domains/published/by_name/${encodeURIComponent(callback.url.hostname)}/`
    const session = isPreview
      ? getCookie(event, getBuilderPreviewSsrCookieName(config))
      : null
    try {
      const builder = await $fetch(path, {
        baseURL: `${config.privateBackendUrl || config.public.publicBackendUrl}/api/`,
        headers: session
          ? {
              Cookie: `${getBuilderPreviewCookieName(config)}=${encodeURIComponent(session)}`,
            }
          : {},
        retry: 0,
      })
      configuredProvider = builder.user_sources.some(
        (source) =>
          source.id === callback.userSourceId &&
          source.auth_providers.some(
            (provider) =>
              provider.supports_callback && provider.type === callback.provider
          )
      )
    } catch (error) {
      // Unknown builders and expired preview sessions must not install credentials.
      if (![401, 403, 404].includes(error.statusCode || error.status))
        throw error
    }
  }
  if (configuredProvider) {
    setCookie(
      event,
      getCookieName(
        config,
        isPreview
          ? getBuilderPreviewUserSourceCookieName()
          : userSourceCookieTokenName
      ),
      callback.token,
      getTokenCookieOptions(config, {
        sameSite: 'lax',
        ...(isPreview && {
          cookieUrl: config.public.builderPreviewUrl,
          path: getBuilderPreviewCookiePath(previewBuilderId),
        }),
      })
    )
  }
  setResponseHeader(event, 'Cache-Control', 'no-store')
  setResponseHeader(event, 'Referrer-Policy', 'no-referrer')
  const path = callback.url.pathname.replace(/^\/+/, '/')
  return sendRedirect(event, path + callback.url.search, 303)
})
