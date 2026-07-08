import path from 'path'

const builderPreviewPathPrefix = (
  process.env.NUXT_PUBLIC_BUILDER_PREVIEW_PATH_PREFIX ?? '/builder-preview'
)
  .split('/')
  .filter(Boolean)
  .join('/')

export const routes = [
  {
    name: 'builder-page',
    path: '/builder/:builderId/page/:pageId',
    file: path.resolve(__dirname, 'pages/pageEditor.vue'),
  },
  {
    name: 'application-builder-preview',
    // This route to the preview of the builder page
    path: builderPreviewPathPrefix
      ? `/${builderPreviewPathPrefix}/:pathMatch(.*)*`
      : '/:pathMatch(.*)*',
    file: path.resolve(__dirname, 'pages/publicPage.vue'),
    meta: {
      previewBuilderRoute: true,
      middleware: ['exchangePreviewToken'],
      builderPageMode: 'preview',
    },
  },
  {
    name: 'application-builder-page',
    path: '/:pathMatch(.*)*',
    file: path.resolve(__dirname, 'pages/publicPage.vue'),
    // If publishedBuilderRoute is true, then that route will only be used on a
    // different subdomain.
    meta: { publishedBuilderRoute: true },
  },
  {
    name: 'builder-health-check',
    path: '/_health',
    file: path.resolve(__dirname, '../core/pages/_health.vue'),
    meta: { publishedBuilderRoute: true, previewBuilderRoute: true },
  },
]
