import { getCookieName } from '@baserow/modules/core/utils/cookie'

export const BUILDER_PREVIEW_COOKIE_BASE_NAME = 'baserow_builder_preview'
export const BUILDER_PREVIEW_SSR_COOKIE_BASE_NAME =
  'baserow_builder_preview_ssr'
export const BUILDER_PREVIEW_USER_SOURCE_COOKIE_BASE_NAME =
  'baserow_builder_preview_user_source'
export const BUILDER_PREVIEW_PATH_PREFIX = '/builder/preview'

export const getBuilderPreviewCookieName = (config) =>
  getCookieName(config, BUILDER_PREVIEW_COOKIE_BASE_NAME)

export const getBuilderPreviewSsrCookieName = (config) =>
  getCookieName(config, BUILDER_PREVIEW_SSR_COOKIE_BASE_NAME)

export const getBuilderPreviewCookiePath = (builderId) =>
  `${BUILDER_PREVIEW_PATH_PREFIX}/${builderId}`

export const getBuilderPreviewUserSourceCookieName = () =>
  BUILDER_PREVIEW_USER_SOURCE_COOKIE_BASE_NAME

export const getBuilderPreviewApiPath = (builderId, path) =>
  `builder/preview/${builderId}/${path}`

export const getBuilderPreviewIdFromApiUrl = (url) => {
  const match = url?.match(/(?:^|\/)builder\/preview\/(\d+)(?:\/|$)/)
  return match ? Number(match[1]) : null
}

/**
 * Returns the generic user-source authentication configuration needed by core
 * while a builder preview is active.
 */
export const getBuilderPreviewUserSourceAuthConfig = (
  builder,
  builderPreviewUrl
) => ({
  authenticationUrls: Object.fromEntries(
    builder.user_sources.map(({ id }) => [
      id,
      getBuilderPreviewApiPath(builder.id, `user-sources/${id}/token-auth/`),
    ])
  ),
  refreshUrl: getBuilderPreviewApiPath(builder.id, 'user-source-auth-refresh/'),
  cookieName: getBuilderPreviewUserSourceCookieName(),
  cookieOptions: {
    cookieUrl: builderPreviewUrl,
    path: getBuilderPreviewCookiePath(builder.id),
    sameSite: 'Lax',
  },
})
