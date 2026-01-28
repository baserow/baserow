import {
  defineNuxtModule,
  addPlugin,
  addServerHandler,
  extendViteConfig,
  addComponent,
  extendPages,
  addLayout,
  createResolver,
  addRouteMiddleware,
  addTemplate,
  install,
} from '@nuxt/kit'
import { routes } from './routes'
import { setDefaultResultOrder } from 'node:dns'
import _ from 'lodash'
import defu from 'defu'
import pathe from 'pathe'
import page from '../builder/services/page'
import { parseHostnamesFromUrls } from './utils/url'

import { readFileSync, writeFileSync, mkdirSync } from 'node:fs'
import { createRequire } from 'node:module'

import head from './head'
// import { routes as customRoutes } from './routes'

import { locales } from '../../config/locales.js'

const require = createRequire(import.meta.url)

const langDir = '../../locales'
export default defineNuxtModule({
  meta: {
    // Usually the npm package name of your module
    name: '@baserow/core',
    // The key in `nuxt.config` that holds your module options
    configKey: 'core',
    // Compatibility constraints
    compatibility: {
      // Semver version of supported nuxt versions
      nuxt: '^3.0.0',
    },
  },
  /*moduleDependencies: {
    '@nuxtjs/i18n': {
      defaults: {
        strategy: 'no_prefix',
        defaultLocale: 'en',
        detectBrowserLanguage: {
          useCookie: true,
          cookieKey: 'i18n-language',
        },
        langDir,
        locales: ['en', 'fr'],
        vueI18n: {
          messages: {
            en: { login: { title: 'Translated title' } },
            fr: { login: { title: 'Titre traduit' } },
          },
        },
        trailingSlash: true,
      },
    },
  },*/
  // Default configuration options for your module, can also be a function returning those
  defaults: {},
  // Shorthand sugar to register Nuxt hooks
  hooks: {},
  // The function holding your module logic, it can be asynchronous
  setup(moduleOptions, nuxt) {
    const { resolve } = createResolver(import.meta.url)

    /*nuxt.hook('vue:error', (err, instance, info) => {
      console.error('Vue Error:', err, info)
    })

    nuxt.hook('app:error', (err) => {
      console.error('Nuxt App Error:', err)
    })
    nuxt.hook('router:error', (err) => {
      console.error('Router Error:', err)
    })*/

    // Universal mode
    //nuxt.options.ssr = true

    // Merge du head
    nuxt.options.app.head = _.merge({}, head, nuxt.options.app.head)

    // Alias
    nuxt.options.alias['@baserow'] = resolve('../../')

    // Runtime config
    const BASEROW_PUBLIC_URL = process.env.BASEROW_PUBLIC_URL
    if (BASEROW_PUBLIC_URL) {
      process.env.PUBLIC_BACKEND_URL = BASEROW_PUBLIC_URL
      process.env.PUBLIC_WEB_FRONTEND_URL = BASEROW_PUBLIC_URL
    }

    // Add routes
    extendPages((pages) => {
      pages.push(...routes)
    })

    nuxt.options.runtimeConfig.privateBackendUrl =
      process.env.PRIVATE_BACKEND_URL ?? 'http://backend:8000'

    nuxt.options.runtimeConfig.public = defu(
      nuxt.options.runtimeConfig.public,
      {
        downloadFileViaXhr: process.env.DOWNLOAD_FILE_VIA_XHR ?? '0',
        baserowDisablePublicUrlCheck:
          process.env.BASEROW_DISABLE_PUBLIC_URL_CHECK ?? false,
        publicBackendUrl:
          process.env.PUBLIC_BACKEND_URL ?? 'http://localhost:8000',
        publicWebFrontendUrl:
          process.env.PUBLIC_WEB_FRONTEND_URL ?? 'http://localhost:3000',
        initialTableDataLimit: process.env.INITIAL_TABLE_DATA_LIMIT ?? null,
        hoursUntilTrashPermanentlyDeleted:
          process.env.HOURS_UNTIL_TRASH_PERMANENTLY_DELETED ?? 24 * 3,
        disableAnonymousPublicViewWsConnections:
          process.env.DISABLE_ANONYMOUS_PUBLIC_VIEW_WS_CONNECTIONS ?? '',
        baserowMaxImportFileSizeMb:
          process.env.BASEROW_MAX_IMPORT_FILE_SIZE_MB ?? 512,
        featureFlags: process.env.FEATURE_FLAGS ?? '',
        baserowDisableGoogleDocsFilePreview:
          process.env.BASEROW_DISABLE_GOOGLE_DOCS_FILE_PREVIEW ?? '',
        baserowMaxSnapshotsPerGroup:
          process.env.BASEROW_MAX_SNAPSHOTS_PER_GROUP ?? -1,
        baserowFrontendSameSiteCookie:
          process.env.BASEROW_FRONTEND_SAME_SITE_COOKIE ?? 'lax',
        baserowFrontendJobsPollingTimeoutMs:
          process.env.BASEROW_FRONTEND_JOBS_POLLING_TIMEOUT_MS ?? 2000,
        posthogProjectApiKey: process.env.POSTHOG_PROJECT_API_KEY ?? '',
        posthogHost: process.env.POSTHOG_HOST ?? '',
        baserowEmbeddedShareUrl:
          process.env.BASEROW_EMBEDDED_SHARE_URL ??
          process.env.PUBLIC_WEB_FRONTEND_URL ??
          'http://localhost:3000',
        baserowUsePgFulltextSearch:
          process.env.BASEROW_USE_PG_FULLTEXT_SEARCH ?? 'true',
        integrationLocalBaserowPageSizeLimit: parseInt(
          process.env.BASEROW_INTEGRATION_LOCAL_BASEROW_PAGE_SIZE_LIMIT ?? 200
        ),
        extraPublicWebFrontendHostnames: parseHostnamesFromUrls(
          process.env.BASEROW_EXTRA_PUBLIC_URLS ?? ''
        ),
        baserowBuilderDomains: process.env.BASEROW_BUILDER_DOMAINS
          ? process.env.BASEROW_BUILDER_DOMAINS.split(',')
          : [],

        baserowRowPageSizeLimit: parseInt(
          process.env.BASEROW_ROW_PAGE_SIZE_LIMIT ?? 200
        ),
        baserowUniqueRowValuesSizeLimit:
          process.env.BASEROW_UNIQUE_ROW_VALUES_SIZE_LIMIT ?? 100,
        baserowDisableSupport: process.env.BASEROW_DISABLE_SUPPORT ?? '',
        baserowIntegrationsPeriodicMinuteMin:
          process.env.BASEROW_INTEGRATIONS_PERIODIC_MINUTE_MIN ?? '1',

        /*sentry: {
          config: {
            dsn: process.env.SENTRY_DSN || '',
            environment: process.env.SENTRY_ENVIRONMENT || '',
          },
        },
        BASEROW_DISABLE_PUBLIC_URL_CHECK:
          process.env.BASEROW_DISABLE_PUBLIC_URL_CHECK ?? false,
        PUBLIC_BACKEND_URL:
          process.env.PUBLIC_BACKEND_URL ?? 'http://localhost:8000',
        PUBLIC_WEB_FRONTEND_URL:
          process.env.PUBLIC_WEB_FRONTEND_URL ?? 'http://localhost:3000',
        MEDIA_URL: process.env.MEDIA_URL ?? 'http://localhost:4000/media/',
        INITIAL_TABLE_DATA_LIMIT: process.env.INITIAL_TABLE_DATA_LIMIT ?? null,
        DOWNLOAD_FILE_VIA_XHR: process.env.DOWNLOAD_FILE_VIA_XHR ?? '0',
        HOURS_UNTIL_TRASH_PERMANENTLY_DELETED:
          process.env.HOURS_UNTIL_TRASH_PERMANENTLY_DELETED ?? 24 * 3,
        DISABLE_ANONYMOUS_PUBLIC_VIEW_WS_CONNECTIONS:
          process.env.DISABLE_ANONYMOUS_PUBLIC_VIEW_WS_CONNECTIONS ?? '',
        BASEROW_MAX_IMPORT_FILE_SIZE_MB:
          process.env.BASEROW_MAX_IMPORT_FILE_SIZE_MB ?? 512,
        FEATURE_FLAGS: process.env.FEATURE_FLAGS ?? '',
        BASEROW_DISABLE_GOOGLE_DOCS_FILE_PREVIEW:
          process.env.BASEROW_DISABLE_GOOGLE_DOCS_FILE_PREVIEW ?? '',
        BASEROW_MAX_SNAPSHOTS_PER_GROUP:
          process.env.BASEROW_MAX_SNAPSHOTS_PER_GROUP ?? -1,
        BASEROW_FRONTEND_JOBS_POLLING_TIMEOUT_MS:
          process.env.BASEROW_FRONTEND_JOBS_POLLING_TIMEOUT_MS ?? 2000,
        BASEROW_USE_PG_FULLTEXT_SEARCH:
          process.env.BASEROW_USE_PG_FULLTEXT_SEARCH ?? 'true',
        POSTHOG_PROJECT_API_KEY: process.env.POSTHOG_PROJECT_API_KEY ?? '',
        POSTHOG_HOST: process.env.POSTHOG_HOST ?? '',
        BASEROW_UNIQUE_ROW_VALUES_SIZE_LIMIT:
          process.env.BASEROW_UNIQUE_ROW_VALUES_SIZE_LIMIT ?? 100,
        BASEROW_ROW_PAGE_SIZE_LIMIT: parseInt(
          process.env.BASEROW_ROW_PAGE_SIZE_LIMIT ?? 200
        ),
        INTEGRATION_LOCAL_BASEROW_PAGE_SIZE_LIMIT: parseInt(
          process.env.BASEROW_INTEGRATION_LOCAL_BASEROW_PAGE_SIZE_LIMIT ?? 200
        ),
        BASEROW_BUILDER_DOMAINS: process.env.BASEROW_BUILDER_DOMAINS
          ? process.env.BASEROW_BUILDER_DOMAINS.split(',')
          : [],
        BASEROW_FRONTEND_SAME_SITE_COOKIE:
          process.env.BASEROW_FRONTEND_SAME_SITE_COOKIE ?? 'lax',
        BASEROW_DISABLE_SUPPORT: process.env.BASEROW_DISABLE_SUPPORT ?? '',
        BASEROW_INTEGRATIONS_PERIODIC_MINUTE_MIN:
          process.env.BASEROW_INTEGRATIONS_PERIODIC_MINUTE_MIN ?? '1',*/
      }
    )

    nuxt.hook('i18n:registerModule', (register) => {
      register({
        langDir: resolve('./locales'),
        locales,
      })
    })

    // Load public assets (images and fonts)
    nuxt.hook('nitro:config', async (nitroConfig) => {
      nitroConfig.publicAssets ||= []
      nitroConfig.publicAssets.push({
        baseURL: '/',
        dir: resolve('static'),
      })
    })

    addLayout({ src: resolve('layouts/app.vue'), filename: 'app.vue' }, 'app')
    addLayout(
      { src: resolve('layouts/login.vue'), filename: 'login.vue' },
      'login'
    )

    addPlugin(resolve('plugins/store.js'))
    addPlugin(resolve('plugins/filters.js'))
    addPlugin(resolve('plugins/vuexState.js'))
    addPlugin(resolve('plugin.js'))
    addPlugin(resolve('plugins/global.js'))
    addPlugin(resolve('plugins/i18n.js'))
    addPlugin(resolve('plugins/clientHandler.js'))
    addPlugin(resolve('plugins/priorityBus.js'))
    addPlugin(resolve('plugins/registry.js'))
    addPlugin(resolve('plugins/permissions.js'))
    addPlugin(resolve('plugins/bus.js'))
    addPlugin(resolve('plugins/realTimeHandler.js'))
    addPlugin(resolve('plugins/hasFeature.js'))
    addPlugin(resolve('plugins/featureFlags.js'))
    addPlugin(resolve('plugins/papa.js'))
    addPlugin(resolve('plugins/ensureRender.js'))
    addPlugin(resolve('plugins/version.js'))
    addPlugin(resolve('plugins/posthog.js'))
    addPlugin(resolve('plugins/vueDatepicker.js'))
    //addPlugin(resolve('plugins/router.js'))
    addPlugin(resolve('plugins/routeMounted.js'))
    addPlugin(resolve('plugins/storeRegister.js'))

    addRouteMiddleware({
      name: 'authentication',
      path: resolve('./middleware/authentication'),
      global: true, // make sure the middleware is added to every route
    })

    addRouteMiddleware({
      name: 'settings',
      path: resolve('./middleware/settings'),
    })

    addRouteMiddleware({
      name: 'authenticated',
      path: resolve('./middleware/authenticated'),
    })

    addRouteMiddleware({
      name: 'workspacesAndApplications',
      path: resolve('./middleware/workspacesAndApplications'),
    })

    addRouteMiddleware({
      name: 'pendingJobs',
      path: resolve('./middleware/pendingJobs'),
    })

    addRouteMiddleware({
      name: 'staff',
      path: resolve('./middleware/staff'),
    })

    addRouteMiddleware({
      name: 'impersonate',
      path: resolve('./middleware/impersonate'),
    })

    addRouteMiddleware({
      name: 'urlCheck',
      path: resolve('./middleware/urlCheck'),
    })

    // Changes the stroke-width of the iconoir svg files because this way, we don't
    // have to fork the repository and change it there.
    const iconoirCssPath = require.resolve('iconoir/css/iconoir.css')
    const patchedIconoirPath = resolve('./assets/scss/vendor/iconoir.scss')

    mkdirSync(pathe.dirname(patchedIconoirPath), { recursive: true })
    const originalIconoirCss = readFileSync(iconoirCssPath, 'utf-8')
    const patchedIconoirCss = originalIconoirCss.replace(
      /stroke-width="1\.5"/g,
      'stroke-width="2.0"'
    )
    writeFileSync(patchedIconoirPath, patchedIconoirCss, 'utf-8')

    // Alias the npm import to our patched file
    nuxt.options.alias['iconoir/css/iconoir'] = patchedIconoirPath

    // Add the main scss file which contains all the generic scss code.
    nuxt.options.css.push(resolve('./assets/scss/default.scss'))
  },
})
