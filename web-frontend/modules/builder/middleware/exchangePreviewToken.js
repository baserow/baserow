import {
  defineNuxtRouteMiddleware,
  navigateTo,
  useCookie,
  useNuxtApp,
  useRequestURL,
  useRuntimeConfig,
} from '#imports'

import { unsetToken } from '@baserow/modules/core/utils/auth'
import {
  getBuilderPreviewCookiePath,
  getBuilderPreviewSsrCookieName,
  getBuilderPreviewUserSourceCookieName,
} from '@baserow/modules/core/utils/builderPreview'
import { isSecureURL } from '@baserow/modules/core/utils/string'
import { createBuilderPreviewSessionError } from '@baserow/modules/builder/plugins/previewClientHandler'

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
  builderId,
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
      body: JSON.stringify({
        preview_handoff: handoffCode,
        builder_id: builderId,
      }),
    }
  )

  if (!response.ok) {
    throw new Error(
      `The builder preview handoff could not be exchanged (${response.status}).`
    )
  }

  const {
    preview_session: previewSession,
    expires_in: expiresIn,
    builder_id: receivedBuilderId,
  } = await response.json()
  if (receivedBuilderId !== builderId) {
    throw new Error('The builder preview handoff belongs to another builder.')
  }
  const previewCookie = getCookie(
    getBuilderPreviewSsrCookieName(config, builderId),
    {
      httpOnly: true,
      maxAge: expiresIn,
      path: getBuilderPreviewCookiePath(builderId),
      sameSite: 'lax',
      secure: isSecureURL(config.public.builderPreviewUrl),
    }
  )
  previewCookie.value = previewSession

  return { expiresIn, previewSession }
}

export const exchangePreviewHandoffOnce = (
  nuxtApp,
  handoffCode,
  builderId,
  config,
  exchange = exchangePreviewHandoffInSsr
) => {
  nuxtApp._builderPreviewHandoffExchanges ||= new Map()
  if (!nuxtApp._builderPreviewHandoffExchanges.has(handoffCode)) {
    nuxtApp._builderPreviewHandoffExchanges.set(
      handoffCode,
      exchange(handoffCode, builderId, config)
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
  const builderId = Number(to.params.builderId)

  if (!previewToken && !previewHandoff) {
    return
  }

  // Opening a fresh preview grant resets the user-source session for this
  // builder without affecting simultaneous previews of other builders.
  await unsetToken(nuxtApp, getBuilderPreviewUserSourceCookieName(builderId), {
    path: getBuilderPreviewCookiePath(builderId),
  })

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
    await exchangePreviewHandoffOnce(nuxtApp, previewHandoff, builderId, config)
  } catch {
    throw createBuilderPreviewSessionError(nuxtApp.$i18n)
  }
  return navigateTo(cleanUrl.toString(), {
    external: true,
    redirectCode: 302,
  })
})
