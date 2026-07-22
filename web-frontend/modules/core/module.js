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

import {
  readFileSync,
  writeFileSync,
  mkdirSync,
  readdirSync,
  existsSync,
} from 'node:fs'
import { createHash } from 'node:crypto'
import { createRequire } from 'node:module'

import head from './head'

import { locales } from '../../config/locales.js'

const require = createRequire(import.meta.url)

// Over-matching (any icon="..." prop) is safe: unknown names simply match no rule.
const ICON_NAME_PATTERNS = [
  /iconoir-([a-z0-9]+(?:-[a-z0-9]+)*)/g,
  /icon=["']([a-z0-9]+(?:-[a-z0-9]+)*)["']/g,
  /icon: ?["']([a-z0-9]+(?:-[a-z0-9]+)*)["']/g,
]

function collectUsedIconoirNames(roots) {
  const names = new Set()
  const walk = (dir) => {
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      const full = pathe.join(dir, entry.name)
      if (entry.isDirectory()) {
        if (entry.name !== 'node_modules' && entry.name !== 'vendor') {
          walk(full)
        }
      } else if (/\.(vue|js|scss)$/.test(entry.name)) {
        const source = readFileSync(full, 'utf-8')
        for (const pattern of ICON_NAME_PATTERNS) {
          for (const match of source.matchAll(pattern)) {
            names.add(match[1])
          }
        }
      }
    }
  }
  for (const root of roots) {
    if (existsSync(root)) {
      walk(root)
    }
  }
  return names
}

export default defineNuxtModule({
  meta: {
    // Usually the npm package name of your module
    name: '@baserow/core',
    // The key in `nuxt.config` that holds your module options
    configKey: 'core',
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
        baserowPresenceVisibleUsers: '3',
        baserowDisableGoogleDocsFilePreview: '',
        baserowMaxSnapshotsPerGroup: -1,
        baserowFrontendSameSiteCookie: 'lax',
        baserowFrontendCookiePrefix: '',
        baserowFrontendJobsPollingTimeoutMs: 2000,
        posthogProjectApiKey: '',
        posthogHost: '',
        baserowEmbeddedShareUrl: 'http://localhost:3000',
        baserowUsePgFulltextSearch: 'true',
        integrationLocalBaserowPageSizeLimit: 200,
        formulaRangeMaxItems: 10000,
        integrationLocalBaserowBatchOperationSizeLimit: 1000,
        extraPublicWebFrontendHostnames: [],
        baserowBuilderDomains: [],
        baserowRowPageSizeLimit: 200,
        baserowUniqueRowValuesSizeLimit: 100,
        baserowMaxFieldTextLength: 1_000_000,
        baserowDisableSupport: '',
        baserowIntegrationsPeriodicMinuteMin: '1',
        mediaUrl: 'http://localhost:4000/media/',
        sentryDsn: '',
        sentryEnvironment: '',
        sentryTracesSampleRate: '0.01',
        sentryReplaysOnErrorSampleRate: '0.1',
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
    addPlugin({ src: resolve('plugins/realTimeHandler.js'), mode: 'client' })
    addPlugin(resolve('plugins/hasFeature.js'))
    addPlugin(resolve('plugins/featureFlags.js'))
    addPlugin(resolve('plugins/papa.js'))
    addPlugin({ src: resolve('plugins/ensureRender.js'), mode: 'client' })
    addPlugin(resolve('plugins/version.js'))
    addPlugin({ src: resolve('plugins/posthog.js'), mode: 'client' })
    addPlugin({ src: resolve('plugins/sentry-user.js'), mode: 'client' })
    addPlugin(resolve('plugins/vueDatepicker.js'))
    addPlugin({ src: resolve('plugins/routeMounted.js'), mode: 'client' })
    addPlugin({ src: resolve('plugins/iconoirRest.js'), mode: 'client' })
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

    addRouteMiddleware({
      name: 'dashboardRedirect',
      path: resolve('./middleware/dashboardRedirect'),
    })

    addRouteMiddleware({
      name: 'redirectCompletedOnboarding',
      path: resolve('./middleware/redirectCompletedOnboarding'),
    })

    // Changes the stroke-width of the iconoir svg files because this way, we don't
    // have to fork the repository and change it there.
    const iconoirCssPath = require.resolve('iconoir/css/iconoir.css')
    // node_modules/.cache survives the buildDir wipe during `nuxt build` and is unwatched.
    const iconoirCacheDir = pathe.join(
      nuxt.options.rootDir,
      'node_modules/.cache/baserow'
    )
    const criticalIconoirPath = pathe.join(iconoirCacheDir, 'iconoir.scss')
    const restIconoirDir = pathe.join(iconoirCacheDir, 'iconoir-public')
    const restIconoirPath = pathe.join(restIconoirDir, 'iconoir-rest.css')

    mkdirSync(restIconoirDir, { recursive: true })
    const patchedIconoirCss = readFileSync(iconoirCssPath, 'utf-8').replace(
      /stroke-width="1\.5"/g,
      'stroke-width="2.0"'
    )

    // Split the catalog: statically-used icons stay render-blocking, the rest
    // (backend-provided names such as template icons) loads asynchronously.
    const usedIconNames = collectUsedIconoirNames([
      resolve('../'),
      resolve('../../../premium/web-frontend/modules'),
      resolve('../../../enterprise/web-frontend/modules'),
    ])
    // The upstream catalog is a single line; slice rules between start offsets.
    const ruleStarts = [
      ...patchedIconoirCss.matchAll(/\.iconoir-([a-z0-9-]+)::before\{/g),
    ].map((match) => ({ name: match[1], index: match.index }))
    const sharedBaseRules = patchedIconoirCss.slice(
      0,
      ruleStarts.length ? ruleStarts[0].index : patchedIconoirCss.length
    )
    const criticalRules = []
    const restRules = []
    ruleStarts.forEach(({ name, index }, i) => {
      const end =
        i + 1 < ruleStarts.length
          ? ruleStarts[i + 1].index
          : patchedIconoirCss.length
      const rule = patchedIconoirCss.slice(index, end)
      ;(usedIconNames.has(name) ? criticalRules : restRules).push(rule)
    })

    const parsedCatalog = criticalRules.length + restRules.length >= 1000
    if (parsedCatalog) {
      writeFileSync(
        criticalIconoirPath,
        sharedBaseRules + criticalRules.join('\n'),
        'utf-8'
      )
      writeFileSync(restIconoirPath, restRules.join('\n'), 'utf-8')
      const restHash = createHash('md5')
        .update(restRules.join('\n'))
        .digest('hex')
        .slice(0, 8)
      nuxt.options.runtimeConfig.public.iconoirRestCssUrl = `/_iconoir/iconoir-rest.css?v=${restHash}`
      nuxt.hook('nitro:config', (nitroConfig) => {
        nitroConfig.publicAssets ||= []
        nitroConfig.publicAssets.push({
          baseURL: '/_iconoir/',
          dir: restIconoirDir,
          maxAge: 3600,
        })
      })
    } else {
      // Unexpected upstream format: keep every icon render-blocking rather than lose any.
      writeFileSync(criticalIconoirPath, patchedIconoirCss, 'utf-8')
      nuxt.options.runtimeConfig.public.iconoirRestCssUrl = ''
    }

    // Alias the npm import to our patched file
    nuxt.options.alias['iconoir/css/iconoir'] = criticalIconoirPath

    // Add the main scss file which contains all the generic scss code.
    nuxt.options.css.push(resolve('./assets/scss/default.scss'))
  },
})
