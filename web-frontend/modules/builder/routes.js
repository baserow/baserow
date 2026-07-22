import path from 'path'

export const routes = [
  {
    name: 'builder-page',
    path: '/builder/:builderId/page/:pageId',
    file: path.resolve(__dirname, 'pages/pageEditor.vue'),
  },
  {
    name: 'builder-health-check',
    path: '/_health',
    file: path.resolve(__dirname, '../core/pages/_health.vue'),
    meta: { publishedBuilderRoute: true, previewBuilderRoute: true },
  },
  {
    name: 'application-builder-preview',
    // The configured preview prefix is only available at runtime in production
    // images, after Nuxt has compiled this route. Match every possible preview
    // path here; the router plugin limits this route to preview requests and the
    // public page strips the runtime prefix before resolving the builder page.
    path: '/:pathMatch(.*)*',
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
]
