import path from 'path'

export default {
  test: {
    env: {
      LC_ALL: 'en_GB.UTF-8',
      LANG: 'en_GB.UTF-8',
      LANGUAGE: 'en_GB',
      TZ: 'UTC',
    },
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
      timezone: 'UTC',
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
}
