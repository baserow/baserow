import { defineVitestConfig } from '@nuxt/test-utils/config'

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
})
