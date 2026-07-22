import { getCookieName } from '@baserow/modules/core/utils/cookie'

export const BUILDER_PREVIEW_COOKIE_BASE_NAME = 'baserow_builder_preview'
export const BUILDER_PREVIEW_SSR_COOKIE_BASE_NAME =
  'baserow_builder_preview_ssr'

export const getBuilderPreviewCookieName = (config, builderId) =>
  getCookieName(config, `${BUILDER_PREVIEW_COOKIE_BASE_NAME}_${builderId}`)

export const getBuilderPreviewSsrCookieName = (config, builderId) =>
  getCookieName(config, `${BUILDER_PREVIEW_SSR_COOKIE_BASE_NAME}_${builderId}`)

export const getBuilderPreviewCookiePath = (builderId) =>
  `/builder-preview/${builderId}`

export const getBuilderPreviewUserSourceCookieName = (builderId) =>
  `user_source_token_${builderId}`
