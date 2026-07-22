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
const PREVIEW_HANDOFF_EXCHANGE_CACHE_TTL_MS = 10_000
// A browser can issue duplicate document requests for the handoff URL. Keep the
// backend exchange promise at module scope so every request handled by this Nitro
// process shares the one-time result.
const previewHandoffExchangeScope = {}

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

export const exchangePreviewHandoff = async (
  handoffCode,
  builderId,
  config,
  fetch = globalThis.fetch
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

  return { expiresIn, previewSession }
}

export const setPreviewHandoffCookie = (
  builderId,
  config,
  { expiresIn, previewSession },
  getCookie = useCookie
) => {
  // Each duplicate SSR response must set its own cookie even though they share the
  // same backend exchange promise.
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
}

export const exchangePreviewHandoffInSsr = async (
  handoffCode,
  builderId,
  config,
  fetch = globalThis.fetch,
  getCookie = useCookie
) => {
  const previewSession = await exchangePreviewHandoff(
    handoffCode,
    builderId,
    config,
    fetch
  )
  setPreviewHandoffCookie(builderId, config, previewSession, getCookie)

  return previewSession
}

export const exchangePreviewHandoffOnce = (
  exchangeScope,
  handoffCode,
  builderId,
  config,
  exchange = exchangePreviewHandoff
) => {
  exchangeScope._builderPreviewHandoffExchanges ||= new Map()
  if (!exchangeScope._builderPreviewHandoffExchanges.has(handoffCode)) {
    const exchangePromise = exchange(handoffCode, builderId, config)
    exchangeScope._builderPreviewHandoffExchanges.set(
      handoffCode,
      exchangePromise
    )
    const scheduleCleanup = () => {
      const cleanupTimer = setTimeout(
        () => exchangeScope._builderPreviewHandoffExchanges.delete(handoffCode),
        PREVIEW_HANDOFF_EXCHANGE_CACHE_TTL_MS
      )
      cleanupTimer.unref?.()
    }
    exchangePromise.then(scheduleCleanup, scheduleCleanup)
  }
  return exchangeScope._builderPreviewHandoffExchanges.get(handoffCode)
}

export const getPreviewHandoffExchangeScope = () => previewHandoffExchangeScope

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
    throw createBuilderPreviewSessionError(nuxtApp.$i18n)
  }

  try {
    const previewSession = await exchangePreviewHandoffOnce(
      getPreviewHandoffExchangeScope(),
      previewHandoff,
      builderId,
      config
    )
    setPreviewHandoffCookie(builderId, config, previewSession)
  } catch {
    throw createBuilderPreviewSessionError(nuxtApp.$i18n)
  }
  return navigateTo(cleanUrl.toString(), {
    external: true,
    redirectCode: 302,
  })
})
