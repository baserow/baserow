import {
  defineEventHandler,
  getRequestURL,
  sendRedirect,
  setCookie,
  setResponseHeader,
} from 'h3'
import { useRuntimeConfig } from 'nitropack/runtime'
import {
  getCookieName,
  getTokenCookieOptions,
  userSourceCookieTokenName,
} from '../../../core/utils/cookie'
import { consumeUserSourceCallback } from '../../../core/utils/userSourceCallback'
import {
  getBuilderPreviewCookiePath,
  getBuilderPreviewUserSourceCookieName,
} from '../../utils/preview'

// Consume the backend callback before Nuxt renders the public page or its payload.
export default defineEventHandler((event) => {
  const callback = consumeUserSourceCallback(getRequestURL(event))
  if (!callback) {
    return
  }

  const config = useRuntimeConfig(event)
  const previewBuilderId = callback.url.pathname.match(
    /^\/builder\/preview\/(\d+)(?:\/|$)/
  )?.[1]
  const isPreview =
    previewBuilderId &&
    [config.public.builderPreviewUrl, config.public.publicWebFrontendUrl].some(
      (url) => url && new URL(url).hostname === callback.url.hostname
    )
  if (callback.token) {
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
  return sendRedirect(event, callback.url.pathname + callback.url.search, 303)
})
