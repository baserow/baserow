import {
  defineNuxtRouteMiddleware,
  navigateTo,
  useCookie,
  useNuxtApp,
  useRequestURL,
  useRuntimeConfig,
} from '#imports'

import {
  unsetToken,
  userSourceCookieTokenName,
} from '@baserow/modules/core/utils/auth'
import {
  getBuilderPreviewCookiePath,
  getBuilderPreviewSsrCookieName,
} from '@baserow/modules/core/utils/builderPreview'
import { isSecureURL } from '@baserow/modules/core/utils/string'
import { createBuilderPreviewSessionError } from '@baserow/modules/builder/plugins/clientHandler'

const PREVIEW_HANDOFF_QUERY_PARAM = 'preview_handoff'

export const getPreviewToken = (to, requestUrl) => {
  const rawPreviewToken = requestUrl.searchParams.get('preview_token')
  const queryPreviewToken = Array.isArray(to.query.preview_token)
    ? to.query.preview_token[0]
    : to.query.preview_token
  return rawPreviewToken || queryPreviewToken
}

export const getPreviewHandoff = (to, requestUrl) => {
  const rawHandoff = requestUrl.searchParams.get(PREVIEW_HANDOFF_QUERY_PARAM)
  const queryHandoff = Array.isArray(to.query[PREVIEW_HANDOFF_QUERY_PARAM])
    ? to.query[PREVIEW_HANDOFF_QUERY_PARAM][0]
    : to.query[PREVIEW_HANDOFF_QUERY_PARAM]
  return rawHandoff || queryHandoff
}

export const getCleanPreviewUrl = (requestUrl, builderPreviewUrl) => {
  const cleanUrl = new URL(
    requestUrl.pathname + requestUrl.search,
    builderPreviewUrl
  )
  cleanUrl.searchParams.delete('preview_token')
  cleanUrl.searchParams.delete(PREVIEW_HANDOFF_QUERY_PARAM)
  return cleanUrl
}

export const exchangePreviewHandoffInSsr = async (
  handoffCode,
  config,
  fetch = globalThis.fetch,
  getCookie = useCookie
) => {
  const response = await fetch(
    `${config.privateBackendUrl.replace(/\/$/, '')}/api/builder/preview/handoff/`,
    {
      method: 'POST',
      headers: {
        Accept: 'application/json',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ preview_handoff: handoffCode }),
    }
  )

  if (!response.ok) {
    throw new Error(
      `The builder preview handoff could not be exchanged (${response.status}).`
    )
  }

  const { preview_session: previewSession, expires_in: expiresIn } =
    await response.json()
  const previewCookie = getCookie(getBuilderPreviewSsrCookieName(config), {
    httpOnly: true,
    maxAge: expiresIn,
    path: getBuilderPreviewCookiePath(config),
    sameSite: 'lax',
    secure: isSecureURL(config.public.builderPreviewUrl),
  })
  previewCookie.value = previewSession

  return { expiresIn, previewSession }
}

export const exchangePreviewHandoffOnce = (
  nuxtApp,
  handoffCode,
  config,
  exchange = exchangePreviewHandoffInSsr
) => {
  nuxtApp._builderPreviewHandoffExchanges ||= new Map()
  if (!nuxtApp._builderPreviewHandoffExchanges.has(handoffCode)) {
    nuxtApp._builderPreviewHandoffExchanges.set(
      handoffCode,
      exchange(handoffCode, config)
    )
  }
  return nuxtApp._builderPreviewHandoffExchanges.get(handoffCode)
}

export default defineNuxtRouteMiddleware(async (to) => {
  const config = useRuntimeConfig()
  const nuxtApp = useNuxtApp()
  const requestUrl = useRequestURL()
  const previewToken = getPreviewToken(to, requestUrl)
  const previewHandoff = getPreviewHandoff(to, requestUrl)

  if (!previewToken && !previewHandoff) {
    return
  }

  // A user-source session belongs to one builder application. Preview URLs all
  // share the same origin, so keeping this cookie when exchanging another
  // preview grant can send the previous builder's token to the new builder.
  await unsetToken(nuxtApp, userSourceCookieTokenName)

  const cleanUrl = getCleanPreviewUrl(
    requestUrl,
    config.public.builderPreviewUrl
  )
  if (previewToken) {
    const exchangeUrl = `${
      config.public.publicBackendUrl
    }/api/builder/preview/exchange/${encodeURIComponent(previewToken)}/`
    return navigateTo(
      `${exchangeUrl}?redirect=${encodeURIComponent(cleanUrl.toString())}`,
      { external: true, redirectCode: 302 }
    )
  }

  if (import.meta.client) {
    return navigateTo(requestUrl.toString(), {
      external: true,
      redirectCode: 302,
    })
  }

  try {
    await exchangePreviewHandoffOnce(nuxtApp, previewHandoff, config)
  } catch {
    throw createBuilderPreviewSessionError(nuxtApp.$i18n)
  }
  return navigateTo(cleanUrl.toString(), {
    external: true,
    redirectCode: 302,
  })
})
