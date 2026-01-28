import { defineVitestConfig } from '@nuxt/test-utils/config'
import path from 'path'

export default defineVitestConfig({
  test: {
    globals: true,
    environment: 'nuxt',
    isolate: true,
    pool: 'forks',
    exclude: [
      '**/node_modules/**',
      '**/.nuxt/**',
      '**/.output/**',
      '**/dist/**',
      '**/build/**',
      '**/coverage/**',
      '**/.git/**',
      '**/.yarn/**',
      '**/.cache/**',
      '**/playwright-report/**',
    ],
    setupFiles: ['./vitest.setup.ts'],
    coverage: {
      provider: 'istanbul',
    },
    environmentOptions: {
      nuxt: {
        domEnvironment: 'happy-dom',
        overrides: {
          i18n: {
            // prevents dynamic importing `.../en.json?import`
            lazy: false,

            defaultLocale: 'en',
            fallbackLocale: 'en',
            locales: [{ code: 'en', name: 'English' }],

            // inline messages so nothing is loaded from disk
            vueI18n: {
              legacy: false,
              locale: 'en',
              messages: { en: {} },
              missingWarn: false,
              fallbackWarn: false,
            },
          },
        },
      },
    },

    include: ['./**/*.spec.js'],
  },
  resolve: {
    alias: {
      '@baserow_test_cases': path.resolve(__dirname, '../tests/cases'),
    },
  },
})
