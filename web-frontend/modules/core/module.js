import path from 'path'
import _ from 'lodash'
import serveStatic from 'serve-static'

import { routes } from './routes'
import head from './head'
import en from './locales/en.json'
import fr from './locales/fr.json'
import nl from './locales/nl.json'
import de from './locales/de.json'
import es from './locales/es.json'
import it from './locales/it.json'
import pl from './locales/pl.json'
import ko from './locales/ko.json'
import { setDefaultResultOrder } from 'dns'
import { parseHostnamesFromUrls } from './utils/url'
const { readFileSync } = require('fs')

export default function CoreModule(options) {
  /**
   * This function adds a plugin, but rather then prepending it to the list it will
   * be appended.
   */
  this.appendPlugin = (template) => {
    this.addPlugin(template)
    this.options.plugins.push(this.options.plugins.splice(0, 1)[0])
  }

  // Baserow must be run in universal mode.
  this.options.mode = 'universal'

  // Ensure in Node 18 `localhost` resolves to `127.0.0.1` and not IPV6 `::1` by default
  // as our internal services are listening on `127.0.0.0` and not `::1`
  setDefaultResultOrder('ipv4first')

  // Prevent automatically loading pages.
  this.nuxt.hook('build:before', () => {
    this.nuxt.options.build.createRoutes = () => {
      return []
    }
  })

  // Set the default head object, but override the configured head.
  // @TODO if a child is a list the new children must be appended instead of overridden.
  this.options.head = _.merge({}, head, this.options.head)

  // Store must be true in order for the store to be injected into the context.
  this.options.store = true

  // Register new alias to the web-frontend directory.
  this.options.alias['@baserow'] = path.resolve(__dirname, '../../')

  const BASEROW_PUBLIC_URL = process.env.BASEROW_PUBLIC_URL
  if (BASEROW_PUBLIC_URL) {
    process.env.PUBLIC_BACKEND_URL = BASEROW_PUBLIC_URL
    process.env.PUBLIC_WEB_FRONTEND_URL = BASEROW_PUBLIC_URL
  }

  // The core depends on these modules.
  this.requireModule('cookie-universal-nuxt')

  this.options.privateRuntimeConfig = {
    PRIVATE_BACKEND_URL:
      process.env.PRIVATE_BACKEND_URL ?? 'http://backend:8000',
  }

  this.options.publicRuntimeConfig = {
    sentry: {
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
    EXTRA_PUBLIC_WEB_FRONTEND_HOSTNAMES: parseHostnamesFromUrls(
      process.env.BASEROW_EXTRA_PUBLIC_URLS ?? ''
    ),
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
      process.env.BASEROW_INTEGRATIONS_PERIODIC_MINUTE_MIN ?? '1',
  }

  this.options.publicRuntimeConfig.BASEROW_EMBEDDED_SHARE_URL =
    process.env.BASEROW_EMBEDDED_SHARE_URL ??
    this.options.publicRuntimeConfig.PUBLIC_WEB_FRONTEND_URL

  this.requireModule([
    '@nuxtjs/sentry',
    {
      // We want the `SENTRY_DSN` environment variable to work on runtime. If a
      // valid DSN is not provided during build, it will build with a mocked
      // instance. To make sure the environment variable is accepted, we must
      // prevent that during build. Providing a fake DSN will have no impact because
      // the environment variable fallback is an empty string, tso then it will be
      // disabled.
      dsn: 'https://public@sentry.com/1',
      clientIntegrations: {
        Dedupe: {},
        ExtraErrorData: {},
        RewriteFrames: {},
        Replay: {},
        ReportingObserver: null,
      },
      clientConfig: {
        replaysSessionSampleRate: 0,
        replaysOnErrorSampleRate: 1.0,
        attachProps: true,
        logErrors: true,
      },
    },
  ])

  const locales = [
    { code: 'en', name: 'English', file: 'en.json' },
    { code: 'fr', name: 'Français', file: 'fr.json' },
    { code: 'nl', name: 'Nederlands', file: 'nl.json' },
    { code: 'de', name: 'Deutsch', file: 'de.json' },
    { code: 'es', name: 'Español', file: 'es.json' },
    { code: 'it', name: 'Italiano', file: 'it.json' },
    { code: 'pl', name: 'Polski (Beta)', file: 'pl.json' },
    { code: 'ko', name: '한국인', file: 'ko.json' },
  ]

  this.requireModule([
    '@nuxtjs/i18n',
    {
      strategy: 'no_prefix',
      defaultLocale: 'en',
      detectBrowserLanguage: {
        useCookie: true,
        cookieKey: 'i18n-language',
      },
      locales,
      langDir: path.resolve(__dirname, '../../locales/'),
      lazy: true,
      vueI18n: {
        fallbackLocale: 'en',
        silentFallbackWarn: true,
      },
    },
  ])

  let alreadyExtended = false
  this.nuxt.hook('i18n:extend-messages', function (additionalMessages) {
    if (alreadyExtended) return
    additionalMessages.push({ en, fr, nl, de, es, it, pl, ko })
    alreadyExtended = true
  })

  // Serve the static directory
  // @TODO we might need to change some things here for production. (See:
  //  https://github.com/nuxt/nuxt.js/blob/5a6cde3ebc23f04e89c30a4196a9b7d116b6d675/
  //  packages/server/src/server.js)
  const staticMiddleware = serveStatic(
    path.resolve(__dirname, 'static'),
    this.options.render.static
  )
  this.addServerMiddleware(staticMiddleware)

  this.addLayout(path.resolve(__dirname, 'layouts/error.vue'), 'error')
  this.addLayout(path.resolve(__dirname, 'layouts/app.vue'), 'app')
  this.addLayout(path.resolve(__dirname, 'layouts/login.vue'), 'login')

  this.addPlugin({ src: path.resolve(__dirname, 'plugins/global.js') })
  this.addPlugin({
    src: path.resolve(__dirname, 'plugins/vue2-smooth-scroll.js'),
  })
  this.addPlugin({
    src: path.resolve(__dirname, 'plugins/vueDatepicker.js'),
    ssr: false,
  })
  this.addPlugin({ src: path.resolve(__dirname, 'middleware.js') })

  // Some plugins depends on i18n instance so the plugin must be added
  // after the nuxt-i18n module's plugin
  this.appendPlugin({ src: path.resolve(__dirname, 'plugin.js') })

  // This plugin must be added after nuxt-i18n module's plugingit
  this.appendPlugin({ src: path.resolve(__dirname, 'plugins/i18n.js') })

  // The client handler depends on environment variables so the plugin must be added
  // after the nuxt-env module's plugin.
  this.appendPlugin({
    src: path.resolve(__dirname, 'plugins/clientHandler.js'),
  })
  this.appendPlugin({
    src: path.resolve(__dirname, 'plugins/realTimeHandler.js'),
  })
  this.appendPlugin({
    src: path.resolve(__dirname, 'plugins/hasFeature.js'),
  })
  this.appendPlugin({ src: path.resolve(__dirname, 'plugins/permissions.js') })
  this.appendPlugin({ src: path.resolve(__dirname, 'plugins/featureFlags.js') })
  this.appendPlugin({ src: path.resolve(__dirname, 'plugins/papa.js') })
  this.appendPlugin({ src: path.resolve(__dirname, 'plugins/ensureRender.js') })
  this.appendPlugin({ src: path.resolve(__dirname, 'plugins/posthog.js') })
  this.appendPlugin({ src: path.resolve(__dirname, 'plugins/router.js') })
  this.appendPlugin({ src: path.resolve(__dirname, 'plugins/version.js') })
  this.appendPlugin({ src: path.resolve(__dirname, 'plugins/routeMounted.js') })

  this.extendRoutes((configRoutes) => {
    // Remove all the routes created by nuxt.
    let i = configRoutes.length
    while (i--) {
      if (configRoutes[i].component.includes('/@nuxt/')) {
        configRoutes.splice(i, 1)
      }
    }

    // Add the routes from the ./routes.js.
    configRoutes.push(...routes)
  })

  // Add a default authentication middleware. In order to add a new middleware the
  // middleware.js file has to be changed.
  this.options.router.middleware.push('authentication')

  this.options.router.middleware.push('impersonate')

  // This template will output the contents of the original Iconoir scss file, but
  // it changes increases the default stroke with for all icons.
  const iconoirCSS = readFileSync(
    require.resolve('iconoir/css/iconoir.css')
  ).toString()
  this.addTemplate({
    fileName: 'baserow/iconoir.css',
    src: path.resolve(__dirname, 'templates/iconoir.js'),
    options: { iconoirCSS },
  })

  // Add the main scss file which contains all the generic scss code.
  this.options.css.push(path.resolve(__dirname, 'assets/scss/default.scss'))
}
