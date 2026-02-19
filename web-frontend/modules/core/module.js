import {
  defineNuxtModule,
  addPlugin,
  extendPages,
  addLayout,
  createResolver,
  addRouteMiddleware,
} from '@nuxt/kit'
import { routes } from './routes'
import _ from 'lodash'
import pathe from 'pathe'

import { readFileSync, writeFileSync, mkdirSync } from 'node:fs'
import { createRequire } from 'node:module'

import head from './head'

import { locales } from '../../config/locales.js'

const require = createRequire(import.meta.url)

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
  // Default configuration options for your module, can also be a function returning those
  defaults: {},
  // Shorthand sugar to register Nuxt hooks
  hooks: {},
  // The function holding your module logic, it can be asynchronous
  setup(moduleOptions, nuxt) {
    const { resolve } = createResolver(import.meta.url)

    // Merge du head
    nuxt.options.app.head = _.merge({}, head, nuxt.options.app.head)

    // Alias
    nuxt.options.alias['@baserow'] = resolve('../../')

    // Add routes
    extendPages((pages) => {
      pages.push(...routes)
    })

    // Runtime config defaults - values can be overridden at runtime via NUXT_ prefixed env vars
    // See env-remap.mjs for the env var remapping that enables backwards compatibility
    nuxt.options.runtimeConfig.privateBackendUrl = 'http://backend:8000'

    nuxt.options.runtimeConfig.public = _.defaultsDeep(
      nuxt.options.runtimeConfig.public,
      {
        buildDate: new Date().toISOString(),
        gitCommit: process.env.GITHUB_SHA?.slice(0, 7),
        downloadFileViaXhr: '0',
        baserowDisablePublicUrlCheck: false,
        publicBackendUrl: 'http://localhost:8000',
        publicWebFrontendUrl: 'http://localhost:3000',
        initialTableDataLimit: null,
        hoursUntilTrashPermanentlyDeleted: 24 * 3,
        disableAnonymousPublicViewWsConnections: '',
        baserowMaxImportFileSizeMb: 512,
        featureFlags: '',
        baserowDisableGoogleDocsFilePreview: '',
        baserowMaxSnapshotsPerGroup: -1,
        baserowFrontendSameSiteCookie: 'lax',
        baserowFrontendJobsPollingTimeoutMs: 2000,
        posthogProjectApiKey: '',
        posthogHost: '',
        baserowEmbeddedShareUrl: 'http://localhost:3000',
        baserowUsePgFulltextSearch: 'true',
        integrationLocalBaserowPageSizeLimit: 200,
        extraPublicWebFrontendHostnames: [],
        baserowBuilderDomains: [],
        baserowRowPageSizeLimit: 200,
        baserowUniqueRowValuesSizeLimit: 100,
        baserowDisableSupport: '',
        baserowIntegrationsPeriodicMinuteMin: '1',
        mediaUrl: 'http://localhost:4000/media/',
        sentryDsn: '',
        sentryEnvironment: '',
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
    addPlugin(resolve('plugins/isWebFrontendHostname.js'))

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
