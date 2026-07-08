import {
  defineNuxtRouteMiddleware,
  navigateTo,
  useNuxtApp,
  useRequestEvent,
  useRequestURL,
  useRuntimeConfig,
} from '#imports'
import { appendResponseHeader } from 'h3'

import {
  unsetToken,
  userSourceCookieTokenName,
} from '@baserow/modules/core/utils/auth'

export const getPreviewToken = (to, requestUrl) => {
  const rawPreviewToken = requestUrl.searchParams.get('preview_token')
  const queryPreviewToken = Array.isArray(to.query.preview_token)
    ? to.query.preview_token[0]
    : to.query.preview_token
  return rawPreviewToken || queryPreviewToken
}

export const getCleanPreviewUrl = (requestUrl, builderPreviewUrl) => {
  const cleanUrl = new URL(
    requestUrl.pathname + requestUrl.search,
    builderPreviewUrl
  )
  cleanUrl.searchParams.delete('preview_token')
  return cleanUrl
}

export const canExchangePreviewTokenDuringSsr = (
  requestUrl,
  publicBackendUrl
) => {
  return requestUrl.origin === new URL(publicBackendUrl).origin
}

const getSetCookieHeaders = (headers) => {
  if (typeof headers.getSetCookie === 'function') {
    return headers.getSetCookie()
  }

  const setCookie = headers.get('set-cookie')
  return setCookie ? [setCookie] : []
}

const exchangePreviewTokenInSsr = async (
  event,
  exchangeUrl,
  cleanUrl,
  fetch = globalThis.fetch
) => {
  const response = await fetch(
    `${exchangeUrl}?redirect=${encodeURIComponent(cleanUrl.toString())}`,
    { redirect: 'manual' }
  )

  if (!response.ok && response.status !== 302) {
    return
  }

  for (const setCookie of getSetCookieHeaders(response.headers)) {
    appendResponseHeader(event, 'set-cookie', setCookie)
  }

  return navigateTo(cleanUrl.pathname + cleanUrl.search, { redirectCode: 302 })
}

export default defineNuxtRouteMiddleware(async (to) => {
  const config = useRuntimeConfig()
  const requestUrl = useRequestURL()
  const previewToken = getPreviewToken(to, requestUrl)

  if (!previewToken) {
    return
  }

  // A user-source session belongs to one builder application. Preview URLs all
  // share the same origin, so keeping this cookie when exchanging another
  // preview grant can send the previous builder's token to the new builder.
  await unsetToken(useNuxtApp(), userSourceCookieTokenName)

  const cleanUrl = getCleanPreviewUrl(
    requestUrl,
    config.public.builderPreviewUrl
  )
  const exchangeUrl = `${
    config.public.publicBackendUrl
  }/api/builder/preview/exchange/${encodeURIComponent(previewToken)}/`

  if (import.meta.server) {
    const event = useRequestEvent()

    if (
      event &&
      canExchangePreviewTokenDuringSsr(
        requestUrl,
        config.public.publicBackendUrl
      )
    ) {
      const redirect = await exchangePreviewTokenInSsr(
        event,
        exchangeUrl,
        cleanUrl
      )

      if (redirect) {
        return redirect
      }
    }
  }

  return navigateTo(
    `${exchangeUrl}?redirect=${encodeURIComponent(cleanUrl.toString())}`,
    { external: true, redirectCode: 302 }
  )
})
