import path from 'node:path'
import { defineNuxtConfig } from 'nuxt/config'
import svgLoader from 'vite-svg-loader'
import { nodePolyfills } from 'vite-plugin-node-polyfills'
import { locales } from './locales.js'

function baserowModuleConfig(
  premiumBase = '../premium/web-frontend',
  enterpriseBase = '../enterprise/web-frontend'
) {
  const additionalModulesCsv = process.env.ADDITIONAL_MODULES
  const additionalModules = additionalModulesCsv
    ? additionalModulesCsv
        .split(',')
        .map((m) => m.trim())
        .filter((m) => m !== '')
    : []

  if (additionalModules.length > 0) {
    console.log(`Loading extra plugin modules: ${additionalModules}`)
  }

  const baseModules = [
    `./modules/core/module.js`,
    `./modules/database/module.js`,
    `./modules/dashboard/module.js`,
    `./modules/builder/module.js`,
    `./modules/automation/module.js`,
    `./modules/integrations/module.js`,
  ]

  if (!process.env.BASEROW_OSS_ONLY) {
    baseModules.push(
      premiumBase + '/modules/baserow_premium/module.js',
      enterpriseBase + '/modules/baserow_enterprise/module.js'
    )
  }
  // baseModules.push('@nuxtjs/sentry')

  const modules = baseModules.concat(additionalModules)

  const zipPkgDir = path.dirname(require.resolve('@zip.js/zip.js/package.json'))
  const zipUmdPath = path.join(zipPkgDir, 'dist/zip.min.js')

  return {
    modules,
    zipUmdPath,
  }
}

const baserow = baserowModuleConfig()

export default defineNuxtConfig({
  compatibilityDate: '2025-07-15',
  alias: {
    '@baserow': '',
  },
  css: [],
  // TODO MIG don't load eslint on production even if it's needed for linting
  modules: [...baserow.modules, '@nuxtjs/i18n', '@nuxt/eslint'],
  i18n: {
    strategy: 'no_prefix',
    defaultLocale: 'en',
    detectBrowserLanguage: {
      useCookie: true,
      cookieKey: 'i18n-language',
    },
    langDir: 'locales',
    locales,
    trailingSlash: true,
    vueI18n: './i18n.config.ts',
  },
  nitro: {
    externals: {
      external: ['vuejs3-datepicker'],
    },
  },
  vite: {
    plugins: [
      nodePolyfills({
        include: ['util'],
        // ✅ prevent "process already declared" in Nitro/Node
        globals: {
          process: false,
          Buffer: false,
          global: false,
        },
      }),
      svgLoader(),
    ],
    ssr: {
      noExternal: ['vue-chartjs', 'chart.js'],
    },
    server: {
      sourcemapIgnoreList: (sourcePath) => sourcePath.includes('node_modules'),
    },
    optimizeDeps: {
      // Pre-bundle moment-guess to avoid missing source map warning
      include: ['moment-guess'],
    },
  },
  buildDir: process.env.NUXT_BUILD_DIR || '.nuxt',
  build: {
    transpile: ['vue-chartjs', 'chart.js'],
    cache: true,
    cacheDirectory: process.env.NUXT_CACHE_DIR || 'node_modules/.cache',
  },
  experimental: {
    appManifest: process.env.NODE_ENV !== 'development',
  },
})
