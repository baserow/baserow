// https://nuxt.com/docs/api/configuration/nuxt-config

import path from 'node:path'
import { nodePolyfills } from 'vite-plugin-node-polyfills'

function baserowModuleConfig(
  base = '@',
  premiumBase = '@/../premium/web-frontend',
  enterpriseBase = '@/../enterprise/web-frontend'
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
    //`${base}/modules/core/module.js`,
    `./modules/core/module.js`,
    `./modules/database/module.js`,
    //`${base}/modules/database/module.js`,
    //`${base}/modules/integrations/module.js`,
    //`${base}/modules/builder/module.js`,
    //`${base}/modules/dashboard/module.js`,
    //`${base}/modules/automation/module.js`,
  ]

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
  devtools: { enabled: true },
  alias: {
    '@baserow': '',
  },
  sourcemap: {
    server: false,
    client: false,
  },
  css: [],
  modules: [
    '@/modules/core/module.js',
    '@/modules/database/module.js',
    '@nuxtjs/i18n',
  ],
  i18n: {
    strategy: 'no_prefix',
    defaultLocale: 'en',
    detectBrowserLanguage: {
      useCookie: true,
      cookieKey: 'i18n-language',
    },
    langDir: './locales',
    locales,
    trailingSlash: true,
    vueI18n: './i18n.config.ts',
  },
  vite: {
    plugins: [
      nodePolyfills({
        include: ['util'],
      }),
    ],
  },
})
