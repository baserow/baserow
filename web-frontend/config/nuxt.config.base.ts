import path from 'node:path'
import { defineNuxtConfig } from 'nuxt/config'
import svgLoader from 'vite-svg-loader'
import { nodePolyfills } from 'vite-plugin-node-polyfills'

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
    /*baseModules.push(
      premiumBase + '/modules/baserow_premium/module.js'
      //enterpriseBase + '/modules/baserow_enterprise/module.js'
    )*/
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

const locales = [
  { code: 'en', name: 'English', file: 'en.json' },
  { code: 'fr', name: 'Français', file: 'fr.json' },
  { code: 'nl', name: 'Nederlands', file: 'nl.json' },
  { code: 'de', name: 'Deutsch', file: 'de.json' },
  { code: 'es', name: 'Español', file: 'es.json' },
  { code: 'it', name: 'Italiano', file: 'it.json' },
  { code: 'pl', name: 'Polski (Beta)', file: 'pl.json' },
]

export default defineNuxtConfig({
  compatibilityDate: '2025-07-15',
  alias: {
    '@baserow': '',
  },
  css: [],
  modules: [...baserow.modules, '@nuxtjs/i18n', '@nuxtjs/storybook'],
  i18n: {
    strategy: 'no_prefix',
    defaultLocale: 'en',
    detectBrowserLanguage: {
      useCookie: true,
      cookieKey: 'i18n-language',
    },
    langDir: './locales',
    restructureDir: '../i18n',
    locales,
    trailingSlash: true,
    vueI18n: './i18n.config.ts',
  },
  storybook: {
    host: 'http://localhost',
    port: 6006,
  },
  vite: {
    plugins: [
      nodePolyfills({
        include: ['util'],
      }),
      svgLoader(),
    ],
  },
})
