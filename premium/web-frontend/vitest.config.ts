import { defineVitestConfig } from '@nuxt/test-utils/config'
import path from 'path'

export default defineVitestConfig({
  test: {
    globals: true,
    environment: 'nuxt',
    setupFiles: ['../web-frontend/vitest.setup.ts'],
    environmentOptions: {
      nuxt: {
        domEnvironment: 'happy-dom',
      },
    },
    include: ['../premium/web-frontend/test/**/*.{test,spec}.{js,ts}'],
    coverage: {
      allowExternal: true,
      reporter: ['text-summary', ['cobertura', { projectRoot: '/baserow/' }]],
      include: [
        '**/*.{js,vue}',
        '../premium/**/*.{js,vue}',
        '../enterprise/**/*.{js,vue}',
      ],
      exclude: [
        '**/node_modules/**',
        '**/.nuxt/**',
        '**/reports/**',
        '**/test/**',
        '**/generated/**',
      ],
      // Optional: sometimes useful with source maps/transforms
      // excludeAfterRemap: true,
    },
  },

  resolve: {
    alias: {
      '@baserow_premium_test': path.resolve(__dirname, '../test/'),
    },
  },
})
