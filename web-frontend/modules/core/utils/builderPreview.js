import { getCookieName } from '@baserow/modules/core/utils/cookie'

export const BUILDER_PREVIEW_COOKIE_BASE_NAME = 'baserow_builder_preview'
export const BUILDER_PREVIEW_SSR_COOKIE_BASE_NAME =
  'baserow_builder_preview_ssr'

export const getBuilderPreviewCookieName = (config) =>
  getCookieName(config, BUILDER_PREVIEW_COOKIE_BASE_NAME)

export const getBuilderPreviewSsrCookieName = (config) =>
  getCookieName(config, BUILDER_PREVIEW_SSR_COOKIE_BASE_NAME)

export const getBuilderPreviewCookiePath = (config) => {
  const path = (config.public.builderPreviewPathPrefix || '')
    .split('/')
    .filter(Boolean)
    .join('/')
  return path ? `/${path}` : '/'
}
