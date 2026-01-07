import { defineVitestConfig } from '@nuxt/test-utils/config'
import path from 'path'

export default defineVitestConfig({
  test: {
    globals: true,
    environment: 'nuxt',
    setupFiles: ['./vitest.setup.ts'],
    environmentOptions: {
      nuxt: {
        domEnvironment: 'happy-dom',
      },
    },
    include: ['./**/*.spec.js'],
  },
  resolve: {
    alias: {
      // @baserow_test_cases/*
      '@baserow_test_cases': path.resolve(__dirname, '../tests/cases'),
    },
  },
})
