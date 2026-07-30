import path from 'node:path'
import { defineNuxtConfig } from 'nuxt/config'
import svgLoader from 'vite-svg-loader'
import { nodePolyfills } from 'vite-plugin-node-polyfills'
import { locales } from './locales.js'
import pkg from '../package.json'

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

  const modules = baseModules.concat(additionalModules)

  const zipPkgDir = path.dirname(require.resolve('@zip.js/zip.js/package.json'))
  const zipUmdPath = path.join(zipPkgDir, 'dist/zip.min.js')

  return {
    modules,
    zipUmdPath,
  }
}

const baserow = baserowModuleConfig()
const frontendCookiePrefix =
  process.env.BASEROW_FRONTEND_COOKIE_PREFIX ||
  process.env.NUXT_PUBLIC_BASEROW_FRONTEND_COOKIE_PREFIX ||
  ''

export default defineNuxtConfig({
  compatibilityDate: '2025-11-15',
  // Nuxt 4 defaults to srcDir "app/"; keep v3-style layout (app.vue and modules at project root).
  srcDir: '.',
  alias: {
    '@baserow': '',
  },
  css: [],
  runtimeConfig: {
    public: {
      version: pkg.version,
    },
  },
  modules: [...baserow.modules, '@nuxtjs/i18n', '@sentry/nuxt/module'],
  i18n: {
    strategy: 'no_prefix',
    defaultLocale: 'en',
    langDir: 'locales',
    locales,
    trailingSlash: true,
    detectBrowserLanguage: {
      useCookie: true,
      cookieKey: `${frontendCookiePrefix}i18n-language`,
      redirectOn: 'root',
    },
    vueI18n: './i18n.config.ts',
  },
  nitro: {
    externals: {
      external: ['vuejs3-datepicker'],
    },
  },
  vite: {
    resolve: {
      // Vue keeps render state in module-level variables. Loading more than one
      // physical runtime makes helpers such as renderSlot observe a different
      // currentRenderingInstance and can crash during hydration or HMR.
      dedupe: ['vue'],
    },
    css: {
      preprocessorOptions: {
        scss: {
          // TODO: Migrate all @import rules to @use/@forward (Dart Sass 3.0 will remove @import).
          //  Also fix global-builtin (unquote → string.unquote in colors.module.scss)
          //  and if-function (old if() syntax in abstracts/_helpers.scss).
          //  See https://sass-lang.com/d/import for the migration guide and automated migrator.
          silenceDeprecations: [
            'import',
            'global-builtin',
            'if-function',
            'color-functions',
          ],
        },
      },
    },
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
      watch: {
        ignored: [
          '**/node_modules/**',
          '**/.git/**',
          '**/.nuxt/**',
          '**/.claude/**',
        ],
      },
    },
    optimizeDeps: {
      // Pre-bundle to avoid page reloads
      include: [
        'moment-guess',
        '@vue/devtools-core',
        '@vue/devtools-kit',
        'vuex',
        'vuejs3-datepicker',
        'posthog-js',
        'flush-promises', // CJS
        'papaparse', // CJS
        'mitt',
        'axios',
        'lodash', // CJS
        'bignumber.js',
        'path-to-regexp', // CJS
        'lodash/get', // CJS
        'lodash/debounce', // CJS
        'ulid',
        'jwt-decode',
        'tldjs', // CJS
        'moment-timezone', // CJS
        'moment/dist/locale/fr',
        'moment/dist/locale/nl',
        'moment/dist/locale/de',
        'moment/dist/locale/es',
        'moment/dist/locale/it',
        'moment/dist/locale/pl',
        'moment/dist/locale/ko',
        'moment/dist/locale/uk',
        'markdown-it',
        '@vuelidate/validators',
        '@tiptap/vue-3',
        '@tiptap/core',
        '@vuelidate/core',
        'thenby', // CJS
        'js-sha256', // CJS
        'async-mutex',
        '@tiptap/markdown',
        '@tiptap/extension-placeholder',
        '@tiptap/extension-document',
        '@tiptap/extension-paragraph',
        '@tiptap/extension-hard-break',
        '@tiptap/extension-heading',
        '@tiptap/extension-list-item',
        '@tiptap/extension-bullet-list',
        '@tiptap/extension-ordered-list',
        '@tiptap/extension-bold',
        '@tiptap/extension-italic',
        '@tiptap/extension-strike',
        '@tiptap/extension-link',
        '@tiptap/extension-underline',
        '@tiptap/extension-subscript',
        '@tiptap/extension-superscript',
        '@tiptap/extension-blockquote',
        '@tiptap/extension-code-block',
        '@tiptap/extension-horizontal-rule',
        '@tiptap/extension-task-item',
        '@tiptap/extension-task-list',
        '@tiptap/extension-text',
        '@tiptap/extension-dropcursor',
        '@tiptap/extension-gapcursor',
        '@tiptap/extension-history',
        'markdown-it-task-lists', // CJS
        'antlr4', // CJS
        'lowlight',
        'highlight.js/lib/languages/javascript',
        'highlight.js/lib/languages/css',
        '@tiptap/extension-code-block-lowlight',
        'moment',
        '@tiptap/vue-3/menus',
        'markdown-it-regexp', // CJS
        '@tiptap/extension-mention',
        '@tiptap/pm/state',
        '@tiptap/extension-image',
        'tippy.js',
        'lodash/extend', // CJS
        'prosemirror-state',
        '@tiptap/pm/model',
        '@vue-flow/core',
        '@vue-flow/background',
        '@vue-flow/controls',
        '@zip.js/zip.js',
        'chartjs-adapter-moment',
        'xlsx',
        '@tiptap/pm/transform',
        '@sentry/core',
        'lodash/isObject',
      ],
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
  vue: {
    compilerOptions: {
      comments: false,
    },
  },
})
