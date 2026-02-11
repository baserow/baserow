import baseConfig from '../../web-frontend/vitest.config.base'

import { defineVitestConfig } from '@nuxt/test-utils/config'
import path from 'path'

export default defineVitestConfig({
  test: {
    ...baseConfig.test,
    setupFiles: ['../web-frontend/vitest.setup.ts'],
    include: ['../premium/web-frontend/test/**/*.{test,spec}.{js,ts}'],
  },

  resolve: {
    alias: {
      '@baserow_premium_test': path.resolve(__dirname, './test/'),
    },
  },
})
